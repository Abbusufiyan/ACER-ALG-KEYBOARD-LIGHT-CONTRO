// SPDX-License-Identifier: GPL-2.0

/*
 * alg_rgb.c
 *
 * ALG RGB Driver
 * --------------
 *
 * Linux kernel driver for Acer laptop RGB keyboards exposed through
 * the CLV0001 ACPI device.
 *
 * Reverse engineered from Acer's Windows AcpiBridge.sys driver.
 *
 * ---------------------------------------------------------------------------
 * DISCOVERY NOTES
 * ---------------------------------------------------------------------------
 *
 * Windows communicates with the keyboard through:
 *
 *     ACPI Device: CLV0001
 *
 * Linux exposes this device as:
 *
 *     \_SB.DCHU
 *
 * The Windows driver sends a _DSM() call using:
 *
 *     UUID:
 *         93f224e4-fbdc-4bbf-add6-db71bdc0afad
 *
 *     Function:
 *         0x67
 *
 * The payload is a 4-byte buffer:
 *
 *     Byte 0 = Green
 *     Byte 1 = Red
 *     Byte 2 = Blue
 *     Byte 3 = Zone / Command (0xF0)
 *
 * Example:
 *
 *     Red:
 *         00 FF 00 F0
 *
 *     Green:
 *         FF 00 00 F0
 *
 *     Blue:
 *         00 00 FF F0
 *
 *     Yellow:
 *         CC FF 00 F0
 *
 * ---------------------------------------------------------------------------
 * SAFETY & HARDWARE SEPARATION
 * ---------------------------------------------------------------------------
 *
 * This driver isolates keyboard lighting and fan control into separate
 * character device interfaces to prevent command collisions:
 *
 *     /dev/alg_rgb -> ACPI Function 0x67 (RGB Keyboard Backlight)
 *     /dev/alg_fan -> ACPI Functions 0x68 & 0x69 (Dual Fan Speed Control)
 *
 * ---------------------------------------------------------------------------
 * USERSPACE API
 * ---------------------------------------------------------------------------
 *
 * 1. Keyboard RGB Lighting (/dev/alg_rgb):
 *     echo red    > /dev/alg_rgb
 *     echo green  > /dev/alg_rgb
 *     echo blue   > /dev/alg_rgb
 *     echo off    > /dev/alg_rgb
 *
 * 2. Fan Speed Control (/dev/alg_fan):
 *     echo auto        > /dev/alg_fan  (Restore firmware closed-loop control)
 *     echo 50 50       > /dev/alg_fan  (Set Fan 1 to 50%, Fan 2 to 50%)
 *     echo manual 70 80> /dev/alg_fan  (Set Fan 1 to 70%, Fan 2 to 80%)
 *
 * All inputs are validated and clamped in kernel space. Minimum duty is
 * clamped to 25% (raw 64) to prevent motor stall and heat buildup.
 *
 * ---------------------------------------------------------------------------
 */

#include <linux/module.h>
#include <linux/acpi.h>
#include <linux/uuid.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/device.h>
#include <linux/string.h>
#include <linux/delay.h>
#include "../include/version.h"

#define DEVICE_NAME "alg_rgb"
#define FAN_DEVICE_NAME "alg_fan"
#define CLASS_NAME "alg"

/*
 * Character device major numbers.
 * Assigned dynamically during module load.
 */
static int major;
static int major_fan;

/*
 * Device class used to create:
 *     /dev/alg_rgb
 *     /dev/alg_fan
 */
static struct class *alg_class;

/*
 * Handle to:
 *     \_SB.DCHU
 * The CLV0001 ACPI device.
 */
static acpi_handle dchu_handle;

/* Diagnostic state tracking */
#define ALG_STATUS_UNTESTED (-ENODATA)
static int last_acpi_status = ALG_STATUS_UNTESTED;
static char last_applied_color[32] = "none";
static int last_applied_brightness = -1;
static bool backlight_is_on = false;

/* Fan state tracking */
static int last_fan_acpi_status = ALG_STATUS_UNTESTED;
static bool fan_manual_active = false;
static u8 last_fan1_duty = 0; // CPU
static u8 last_fan2_duty = 0; // GPU



/*
 * CLV0001 RGB control UUID.
 *
 * Extracted from Acer's Windows AcpiBridge.sys driver.
 */
static guid_t rgb_guid = GUID_INIT(
    0x93f224e4,
    0xfbdc,
    0x4bbf,
    0xad, 0xd6, 0xdb, 0x71, 0xbd, 0xc0, 0xaf, 0xad);

/*
 * Firmware color entry.
 *
 * IMPORTANT:
 *
 * The firmware expects:
 *
 *     G R B
 *
 * NOT:
 *
 *     R G B
 *
 * The values below are stored in firmware order.
 */
struct alg_color
{
    const char *name;

    u8 g;
    u8 r;
    u8 b;
};

/*
 * Known-good colors.
 *
 * Add new colors here as they are discovered.
 *
 * Example:
 *
 *     { "orange", 0x80, 0xFF, 0x00 },
 */
static const struct alg_color colors[] = {
    {"off", 0x00, 0x00, 0x00},

    {"red", 0x00, 0xFF, 0x00},
    {"orange", 0x7F, 0xFF, 0x00},
    {"yellow", 0xFF, 0xFF, 0x00},

    {"lime", 0xFF, 0x7F, 0x00},
    {"light-green", 0xFF, 0x3F, 0x00},
    {"green", 0xFF, 0x00, 0x00},

    {"green-cyan", 0xFF, 0x00, 0x46},
    {"cyan", 0xFF, 0x00, 0xC8},

    {"light-blue", 0x7F, 0x00, 0xC8},
    {"blue", 0x00, 0x00, 0xC8},

    {"violet", 0x00, 0x7F, 0xC8},
    {"magenta", 0x00, 0xFF, 0xC8},
    {"pink", 0x00, 0xFF, 0x7F},

    {"flesh", 0x7F, 0xFF, 0x3F},

    {"bluish-white", 0x7F, 0x3F, 0x7F},

    {"white", 0xFF, 0xFF, 0xFF},
};

/*
 * Acer firmware brightness levels.
 *
 * Reverse engineered from Windows captures.
 */
static const u8 brightness_levels[] = {
    0x00,
    0x2F,
    0x5F,
    0x8F,
    0xBF};

/*
 * Send a color packet to firmware.
 *
 * Packet layout:
 *
 *     [0] Green
 *     [1] Red
 *     [2] Blue
 *     [3] 0xF0
 *
 * The packet is wrapped in an ACPI package and passed to:
 *
 *     DCHU._DSM()
 *
 * using:
 *
 *     Function = 0x67
 */
static int send_packet(u8 b0, u8 b1, u8 b2, u8 b3)
{
    union acpi_object *out;
    u8 rgb_buf[4] = { b0, b1, b2, b3 };
    union acpi_object buf_obj;
    union acpi_object pkg_obj;
    union acpi_object pkg_elements[1];
    int ret = 0;

    if (!dchu_handle) {
        last_acpi_status = -ENODEV;
        return -ENODEV;
    }

    buf_obj.type = ACPI_TYPE_BUFFER;
    buf_obj.buffer.length = sizeof(rgb_buf);
    buf_obj.buffer.pointer = rgb_buf;

    pkg_elements[0] = buf_obj;

    pkg_obj.type = ACPI_TYPE_PACKAGE;
    pkg_obj.package.count = 1;
    pkg_obj.package.elements = pkg_elements;

    out = acpi_evaluate_dsm(
        dchu_handle,
        &rgb_guid,
        0,
        0x67,
        &pkg_obj);

    if (!out) {
        pr_err_ratelimited("alg-rgb: ACPI _DSM evaluate failed (NULL) for [%02x %02x %02x %02x]\n",
                           b0, b1, b2, b3);
        last_acpi_status = -EIO;
        return -EIO;
    }

    if (out->type == ACPI_TYPE_INTEGER) {
        if (out->integer.value == 0x80000002) {
            pr_err_ratelimited("alg-rgb: ACPI _DSM returned unsupported (0x80000002)\n");
            ret = -EOPNOTSUPP;
        } else if (out->integer.value != 0x67) {
            pr_warn_ratelimited("alg-rgb: ACPI _DSM returned unexpected status 0x%llx\n",
                                (unsigned long long)out->integer.value);
            ret = -EPROTO;
        } else {
            ret = 0;
        }
    } else {
        pr_err_ratelimited("alg-rgb: ACPI _DSM returned unexpected non-integer type %d\n", out->type);
        ret = -EBADMSG;
    }


    ACPI_FREE(out);
    last_acpi_status = ret;
    return ret;
}

static int send_color(

    const struct alg_color *c,
    int brightness)
{
    /*
     * Acer ALG / Clevo EC keyboard backlight command sequence:
     * Discovered and validated from decompiled DSDT method \_SB.DCHU.SCMD:
     *
     * 1. Power ON/OFF: Function 0x67 with Byte 3 = 0x40 (Local7 == 0x04)
     *    In SCMD: Local3 = (ARGS >> 16) & 0xFF (Byte 2).
     *    - If Local3 != 0: sends EC command [0x02, 0x00, 0xC4, 0x0D] (Power ON)
     *    - If Local3 == 0: sends EC command [0x02, 0x00, 0xC4, 0x0E] (Power OFF)
     *    Power ON packet:  [0x00, 0x00, 0x01, 0x40]
     *    Power OFF packet: [0x00, 0x00, 0x00, 0x40]
     *
     * 2. Hardware PWM Brightness: Function 0x67 with Byte 3 = 0xD0 (Local7 == 0x0D)
     *    In SCMD: Local2 = (Byte1 >> 4) & 0x0F. PWM = 0xFF - (Local2 * 25).
     *    Sends EC command [0x03, 0x00, 0xC4, 0x02, PWM].
     *    bright_nibbles: { 0x80 (55), 0x60 (105), 0x40 (155), 0x20 (205), 0x00 (255) }
     *
     * 3. RGB Color: Function 0x67 with Byte 3 = 0xFX (Local7 == 0x0F)
     *    In SCMD: Local4 = Byte 3 & 0x0F.
     *    - 0xF0: Local4 = 0 -> EC command [0x05, 0x00, 0xCA, 0x03, B, R, G] (Zone 1)
     *    - 0xF3: Local4 = 3 -> EC command [0x05, 0x00, 0xCA, 0x07, B, R, G] (All Zones)
     */
    static const u8 bright_nibbles[5] = { 0x80, 0x60, 0x40, 0x20, 0x00 };
    int ret;

    if (brightness < 0)
        brightness = 0;

    if (brightness > 4)
        brightness = 4;

    if (!strcmp(c->name, "off") || brightness == 0) {
        // Set LED color to black across all zones
        ret = send_packet(0x00, 0x00, 0x00, 0xF3);
        if (ret < 0)
            return ret;

        // Set LED color to black for zone 1
        ret = send_packet(0x00, 0x00, 0x00, 0xF0);
        if (ret < 0)
            return ret;

        // Turn off backlight power rail (EC command C4 0E)
        ret = send_packet(0x00, 0x00, 0x00, 0x40);
        if (ret < 0)
            return ret;

        backlight_is_on = false;
        strscpy(last_applied_color, "off", sizeof(last_applied_color));
        last_applied_brightness = 0;
        pr_info("alg-rgb: backlight power OFF\n");
        return 0;
    }

    // 1. Send Power-ON packet: [0x00, 0x00, 0x01, 0x40] -> EC command C4 0D
    ret = send_packet(0x00, 0x00, 0x01, 0x40);
    if (ret < 0)
        return ret;

    // Small delay (1ms) between EC mailbox writes
    usleep_range(1000, 2000);

    // 2. Send Global Brightness PWM packet: [0x00, bright_nibbles[brightness], 0x00, 0xD0] -> EC command C4 02
    ret = send_packet(0x00, bright_nibbles[brightness], 0x00, 0xD0);
    if (ret < 0)
        return ret;

    usleep_range(1000, 2000);

    // 3. Send All-Zone RGB Color packet: [G, R, B, 0xF3] -> EC command CA 07
    ret = send_packet(c->g, c->r, c->b, 0xF3);
    if (ret < 0)
        return ret;

    usleep_range(1000, 2000);

    // 4. Also send Zone-1 RGB Color packet: [G, R, B, 0xF0] -> EC command CA 03
    ret = send_packet(c->g, c->r, c->b, 0xF0);
    if (ret < 0)
        return ret;

    backlight_is_on = true;
    strscpy(last_applied_color, c->name, sizeof(last_applied_color));
    last_applied_brightness = brightness;

    pr_info("alg-rgb: applied color '%s' brightness=%d\n", c->name, brightness);
    return 0;
}

/*
 * Diagnostic read handler for /dev/alg_rgb
 */
static ssize_t alg_read(
    struct file *file,
    char __user *buf,
    size_t count,
    loff_t *ppos)
{
    char diag_buf[512];
    const char *status_str;
    int len;

    if (last_acpi_status == ALG_STATUS_UNTESTED)
        status_str = "UNTESTED (no ACPI commands issued yet)";
    else if (last_acpi_status == 0)
        status_str = "SUCCESS (firmware accepted last call)";
    else if (last_acpi_status == -EOPNOTSUPP)
        status_str = "UNSUPPORTED (firmware returned 0x80000002)";
    else if (last_acpi_status == -EPROTO)
        status_str = "PROTOCOL_ERROR (unexpected integer return value)";
    else if (last_acpi_status == -EBADMSG)
        status_str = "BAD_MESSAGE (firmware returned non-integer object)";
    else if (last_acpi_status == -EIO)
        status_str = "IO_ERROR (acpi_evaluate_dsm returned NULL)";
    else
        status_str = "FAILED";

    len = scnprintf(diag_buf, sizeof(diag_buf),
        "driver_version: %s\n"
        "acpi_device: \\_SB.DCHU (CLV0001)\n"
        "acpi_handle_bound: %s\n"
        "last_acpi_status: %d (%s)\n"
        "software_state: %s\n"
        "last_requested_color: %s\n"
        "last_requested_brightness: %d\n"
        "hardware_confirmation: UNVERIFIED (software execution does not confirm physical LED output)\n",
        ALG_RGB_VERSION_STRING,
        dchu_handle ? "yes" : "no",
        last_acpi_status,
        status_str,
        backlight_is_on ? "ON" : (last_acpi_status == ALG_STATUS_UNTESTED ? "UNKNOWN" : "OFF"),
        last_applied_color,
        last_applied_brightness);

    return simple_read_from_buffer(buf, count, ppos, diag_buf, len);
}


/*
 * Write handler for /dev/alg_rgb
 *
 * Expected input:
 *     <color> [<brightness>]
 *
 * Examples:
 *     red
 *     red 4
 *     cyan 2
 *     off
 */
static ssize_t alg_write(
    struct file *file,
    const char __user *buf,
    size_t len,
    loff_t *off)
{
    char kbuf[64];
    int i;
    int brightness = 4;
    char color_name[32];
    char extra[32];
    int parsed;
    int ret;

    if (len == 0)
        return -EINVAL;

    /* Prevent oversized writes and truncation issues */
    if (len >= sizeof(kbuf))
        return -EINVAL;

    if (copy_from_user(kbuf, buf, len))
        return -EFAULT;

    kbuf[len] = '\0';
    strim(kbuf);

    if (kbuf[0] == '\0')
        return -EINVAL;

    parsed = sscanf(kbuf, "%31s %d %31s", color_name, &brightness, extra);
    if (parsed < 1 || parsed > 2)
        return -EINVAL;

    if (parsed == 2 && (brightness < 0 || brightness > 4))
        return -EINVAL;

    /* Search color table */
    for (i = 0; i < ARRAY_SIZE(colors); i++)
    {
        if (!strcmp(color_name, colors[i].name))
        {
            ret = send_color(&colors[i], brightness);
            if (ret < 0)
                return ret;

            return len;
        }
    }

    pr_err_ratelimited("alg-rgb: unknown color '%s'\n", color_name);
    return -EINVAL;
}

/*
 * Character device operations for RGB.
 */
static const struct file_operations fops = {
    .owner = THIS_MODULE,
    .read = alg_read,
    .write = alg_write,
};

/*
 * ---------------------------------------------------------------------------
 * FAN CONTROL SUBSYSTEM (Functions 0x68 & 0x69)
 * ---------------------------------------------------------------------------
 */

static int send_fan_auto(void)
{
    union acpi_object *out;
    u8 auto_buf[4] = { 0x03, 0x00, 0x00, 0x00 }; /* bitmask 0x03 restores fan 1 and 2 to auto */
    union acpi_object buf_obj;
    union acpi_object pkg_obj;
    union acpi_object pkg_elements[1];
    int ret = 0;

    if (!dchu_handle) {
        last_fan_acpi_status = -ENODEV;
        return -ENODEV;
    }

    buf_obj.type = ACPI_TYPE_BUFFER;
    buf_obj.buffer.length = sizeof(auto_buf);
    buf_obj.buffer.pointer = auto_buf;

    pkg_elements[0] = buf_obj;

    pkg_obj.type = ACPI_TYPE_PACKAGE;
    pkg_obj.package.count = 1;
    pkg_obj.package.elements = pkg_elements;

    out = acpi_evaluate_dsm(
        dchu_handle,
        &rgb_guid,
        0,
        0x69,
        &pkg_obj);

    if (!out) {
        pr_err_ratelimited("alg-fan: ACPI _DSM evaluate failed for auto restore (func 0x69)\n");
        last_fan_acpi_status = -EIO;
        return -EIO;
    }

    if (out->type == ACPI_TYPE_INTEGER) {
        if (out->integer.value == 0x80000002) {
            pr_err_ratelimited("alg-fan: ACPI _DSM returned unsupported (0x80000002)\n");
            ret = -EOPNOTSUPP;
        } else if (out->integer.value != 0x69) {
            pr_warn_ratelimited("alg-fan: ACPI _DSM returned unexpected status 0x%llx for func 0x69\n",
                                (unsigned long long)out->integer.value);
            ret = -EPROTO;
        } else {
            ret = 0;
        }
    } else {
        pr_err_ratelimited("alg-fan: ACPI _DSM returned non-integer type %d\n", out->type);
        ret = -EBADMSG;
    }

    ACPI_FREE(out);
    last_fan_acpi_status = ret;
    if (ret == 0) {
        fan_manual_active = false;
        last_fan1_duty = 0;
        last_fan2_duty = 0;
        pr_info("alg-fan: restored firmware automatic fan control (SCMD 0x69)\n");
    }
    return ret;
}

static int send_fan_duty(u8 cpu_raw, u8 gpu_raw)
{
    union acpi_object *out;
    u8 duty_buf[4];
    union acpi_object buf_obj;
    union acpi_object pkg_obj;
    union acpi_object pkg_elements[1];
    int ret = 0;

    if (!dchu_handle) {
        last_fan_acpi_status = -ENODEV;
        return -ENODEV;
    }

    /* Enforce safety floor: minimum 25% (raw 64) to prevent stall */
    if (cpu_raw < 64)
        cpu_raw = 64;
    if (gpu_raw < 64)
        gpu_raw = 64;

    duty_buf[0] = cpu_raw; /* Fan 1 (CPU) */
    duty_buf[1] = gpu_raw; /* Fan 2 (GPU) */
    duty_buf[2] = 0x00;
    duty_buf[3] = 0x00;

    buf_obj.type = ACPI_TYPE_BUFFER;
    buf_obj.buffer.length = sizeof(duty_buf);
    buf_obj.buffer.pointer = duty_buf;

    pkg_elements[0] = buf_obj;

    pkg_obj.type = ACPI_TYPE_PACKAGE;
    pkg_obj.package.count = 1;
    pkg_obj.package.elements = pkg_elements;

    out = acpi_evaluate_dsm(
        dchu_handle,
        &rgb_guid,
        0,
        0x68,
        &pkg_obj);

    if (!out) {
        pr_err_ratelimited("alg-fan: ACPI _DSM evaluate failed for manual duty (func 0x68)\n");
        last_fan_acpi_status = -EIO;
        return -EIO;
    }

    if (out->type == ACPI_TYPE_INTEGER) {
        if (out->integer.value == 0x80000002) {
            pr_err_ratelimited("alg-fan: ACPI _DSM returned unsupported (0x80000002)\n");
            ret = -EOPNOTSUPP;
        } else if (out->integer.value != 0x68) {
            pr_warn_ratelimited("alg-fan: ACPI _DSM returned unexpected status 0x%llx for func 0x68\n",
                                (unsigned long long)out->integer.value);
            ret = -EPROTO;
        } else {
            ret = 0;
        }
    } else {
        pr_err_ratelimited("alg-fan: ACPI _DSM returned non-integer type %d\n", out->type);
        ret = -EBADMSG;
    }

    ACPI_FREE(out);
    last_fan_acpi_status = ret;
    if (ret == 0) {
        fan_manual_active = true;
        last_fan1_duty = cpu_raw;
        last_fan2_duty = gpu_raw;
        pr_info("alg-fan: applied manual duty CPU=%u%% (raw %u), GPU=%u%% (raw %u)\n",
                (unsigned int)((cpu_raw * 100 + 127) / 255), cpu_raw,
                (unsigned int)((gpu_raw * 100 + 127) / 255), gpu_raw);
    }
    return ret;
}

/*
 * Diagnostic read handler for /dev/alg_fan
 */
static ssize_t alg_fan_read(
    struct file *file,
    char __user *buf,
    size_t count,
    loff_t *ppos)
{
    char diag_buf[512];
    const char *status_str;
    int len;

    if (last_fan_acpi_status == ALG_STATUS_UNTESTED)
        status_str = "UNTESTED (no ACPI fan commands issued yet)";
    else if (last_fan_acpi_status == 0)
        status_str = "SUCCESS (firmware accepted last fan call)";
    else if (last_fan_acpi_status == -EOPNOTSUPP)
        status_str = "UNSUPPORTED (firmware returned 0x80000002)";
    else if (last_fan_acpi_status == -EPROTO)
        status_str = "PROTOCOL_ERROR (unexpected integer return value)";
    else if (last_fan_acpi_status == -EBADMSG)
        status_str = "BAD_MESSAGE (firmware returned non-integer object)";
    else if (last_fan_acpi_status == -EIO)
        status_str = "IO_ERROR (acpi_evaluate_dsm returned NULL)";
    else
        status_str = "FAILED";

    len = scnprintf(diag_buf, sizeof(diag_buf),
        "driver_version: %s\n"
        "acpi_device: \\_SB.DCHU (CLV0001)\n"
        "acpi_handle_bound: %s\n"
        "last_acpi_status: %d (%s)\n"
        "fan_mode: %s\n"
        "fan1_cpu_duty_pct: %u\n"
        "fan1_cpu_duty_raw: %u\n"
        "fan2_gpu_duty_pct: %u\n"
        "fan2_gpu_duty_raw: %u\n",
        ALG_RGB_VERSION_STRING,
        dchu_handle ? "yes" : "no",
        last_fan_acpi_status,
        status_str,
        fan_manual_active ? "MANUAL" : "AUTO",
        fan_manual_active ? (unsigned int)((last_fan1_duty * 100 + 127) / 255) : 0,
        last_fan1_duty,
        fan_manual_active ? (unsigned int)((last_fan2_duty * 100 + 127) / 255) : 0,
        last_fan2_duty);

    return simple_read_from_buffer(buf, count, ppos, diag_buf, len);
}

/*
 * Write handler for /dev/alg_fan
 *
 * Supported commands:
 *   auto
 *   <cpu_pct> <gpu_pct>       (e.g. "50 50")
 *   manual <cpu_pct> <gpu_pct>(e.g. "manual 60 70")
 *   set <cpu_pct> <gpu_pct>   (e.g. "set 80 80")
 */
static ssize_t alg_fan_write(
    struct file *file,
    const char __user *buf,
    size_t len,
    loff_t *off)
{
    char kbuf[64];
    int cpu_val = 0;
    int gpu_val = 0;
    u8 cpu_raw = 64;
    u8 gpu_raw = 64;
    char prefix[32];
    int parsed;
    int ret;

    if (len == 0 || len >= sizeof(kbuf))
        return -EINVAL;

    if (copy_from_user(kbuf, buf, len))
        return -EFAULT;

    kbuf[len] = '\0';
    strim(kbuf);

    if (kbuf[0] == '\0')
        return -EINVAL;

    /* 1. Auto restore command */
    if (!strcmp(kbuf, "auto") || !strcmp(kbuf, "restore") || !strcmp(kbuf, "reset")) {
        ret = send_fan_auto();
        if (ret < 0)
            return ret;
        return len;
    }

    /* 2. Manual duty commands */
    parsed = sscanf(kbuf, "%d %d", &cpu_val, &gpu_val);
    if (parsed == 2) {
        goto apply_duty;
    }

    parsed = sscanf(kbuf, "%31s %d %d", prefix, &cpu_val, &gpu_val);
    if (parsed == 3 && (!strcmp(prefix, "manual") || !strcmp(prefix, "set") || !strcmp(prefix, "duty"))) {
        goto apply_duty;
    }

    pr_err_ratelimited("alg-fan: unrecognized command '%s'\n", kbuf);
    return -EINVAL;

apply_duty:
    /* Convert percentage or raw value to 8-bit raw duty (clamp 25% - 100%) */
    if (cpu_val <= 100)
        cpu_raw = (u8)clamp((cpu_val * 255 + 50) / 100, 64, 255);
    else
        cpu_raw = (u8)clamp(cpu_val, 64, 255);

    if (gpu_val <= 100)
        gpu_raw = (u8)clamp((gpu_val * 255 + 50) / 100, 64, 255);
    else
        gpu_raw = (u8)clamp(gpu_val, 64, 255);

    ret = send_fan_duty(cpu_raw, gpu_raw);
    if (ret < 0)
        return ret;

    return len;
}

static const struct file_operations fan_fops = {
    .owner = THIS_MODULE,
    .read = alg_fan_read,
    .write = alg_fan_write,
};

/*
 * Module initialization.
 */
static int __init alg_init(void)
{
    acpi_status status;
    struct device *dev;
    struct device *fan_dev;

    pr_info("alg-rgb: loading\n");
    pr_info("alg-rgb v%s loaded (RGB & Fan interfaces)\n", ALG_RGB_VERSION_STRING);

    status = acpi_get_handle(
        NULL,
        "\\_SB.DCHU",
        &dchu_handle);

    if (ACPI_FAILURE(status))
    {
        pr_err("alg-rgb: could not locate \\_SB.DCHU\n");
        return -ENODEV;
    }

    /* Register RGB char device */
    major = register_chrdev(
        0,
        DEVICE_NAME,
        &fops);

    if (major < 0)
    {
        pr_err("alg-rgb: failed to register RGB char device\n");
        return major;
    }

    /* Register Fan char device */
    major_fan = register_chrdev(
        0,
        FAN_DEVICE_NAME,
        &fan_fops);

    if (major_fan < 0)
    {
        pr_err("alg-rgb: failed to register Fan char device\n");
        unregister_chrdev(major, DEVICE_NAME);
        return major_fan;
    }

    alg_class = class_create(CLASS_NAME);
    if (IS_ERR(alg_class))
    {
        unregister_chrdev(major_fan, FAN_DEVICE_NAME);
        unregister_chrdev(major, DEVICE_NAME);
        return PTR_ERR(alg_class);
    }

    /* Create /dev/alg_rgb */
    dev = device_create(
        alg_class,
        NULL,
        MKDEV(major, 0),
        NULL,
        DEVICE_NAME);

    if (IS_ERR(dev))
    {
        class_destroy(alg_class);
        unregister_chrdev(major_fan, FAN_DEVICE_NAME);
        unregister_chrdev(major, DEVICE_NAME);
        return PTR_ERR(dev);
    }

    /* Create /dev/alg_fan */
    fan_dev = device_create(
        alg_class,
        NULL,
        MKDEV(major_fan, 0),
        NULL,
        FAN_DEVICE_NAME);

    if (IS_ERR(fan_dev))
    {
        device_destroy(alg_class, MKDEV(major, 0));
        class_destroy(alg_class);
        unregister_chrdev(major_fan, FAN_DEVICE_NAME);
        unregister_chrdev(major, DEVICE_NAME);
        return PTR_ERR(fan_dev);
    }

    pr_info("alg-rgb: loaded successfully (/dev/%s and /dev/%s available)\n",
            DEVICE_NAME, FAN_DEVICE_NAME);
    return 0;
}

/*
 * Module cleanup.
 */
static void __exit alg_exit(void)
{
    /* Safety: if manual mode was active, restore firmware automatic control */
    if (fan_manual_active) {
        send_fan_auto();
    }

    device_destroy(
        alg_class,
        MKDEV(major_fan, 0));

    device_destroy(
        alg_class,
        MKDEV(major, 0));

    class_destroy(alg_class);

    unregister_chrdev(
        major_fan,
        FAN_DEVICE_NAME);

    unregister_chrdev(
        major,
        DEVICE_NAME);

    pr_info("alg-rgb: unloaded\n");
}

module_init(alg_init);
module_exit(alg_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Kaushik Sarkar");
MODULE_DESCRIPTION("ALG RGB and Fan Driver for Acer CLV0001 hardware");
MODULE_VERSION(ALG_RGB_VERSION_STRING);
