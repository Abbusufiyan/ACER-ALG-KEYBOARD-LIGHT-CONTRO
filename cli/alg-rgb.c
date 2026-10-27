// SPDX-License-Identifier: GPL-2.0

#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/utsname.h>

#include "../include/version.h"

static void print_version(void)
{
    printf("alg-rgb %s\n", ALG_RGB_VERSION_STRING);
}

static void usage(const char *prog)
{
    printf("ALG RGB Keyboard Controller (v%s)\n\n", ALG_RGB_VERSION_STRING);

    printf("Usage:\n");
    printf("  %s <color>              Set color at maximum brightness (4)\n", prog);
    printf("  %s <color> <brightness> Set color at specified brightness (0-4)\n", prog);
    printf("  %s -d, --diag           Run system and ACPI diagnostics\n\n", prog);

    printf("Colors:\n");
    printf("  red, orange, yellow, lime, light-green, green, green-cyan,\n");
    printf("  cyan, light-blue, blue, violet, magenta, pink, flesh,\n");
    printf("  bluish-white, white, off\n\n");

    printf("Brightness:\n");
    printf("  0 = off\n");
    printf("  1 = low\n");
    printf("  2 = medium\n");
    printf("  3 = high\n");
    printf("  4 = maximum\n\n");

    printf("Examples:\n");
    printf("  %s red\n", prog);
    printf("  %s red 4\n", prog);
    printf("  %s cyan 2\n", prog);
    printf("  %s white 1\n", prog);
    printf("  %s off\n\n", prog);

    printf("Options:\n");
    printf("  -d, --diag       Run hardware, driver, and ACPI diagnostics\n");
    printf("  -h, --help       Show this help message\n");
    printf("  --version        Show version information\n");
}

static void read_sysfs_string(const char *path, char *out, size_t max)
{
    FILE *f = fopen(path, "r");
    if (!f) {
        snprintf(out, max, "unknown");
        return;
    }
    if (fgets(out, max, f)) {
        size_t l = strlen(out);
        if (l > 0 && out[l - 1] == '\n')
            out[l - 1] = '\0';
    } else {
        snprintf(out, max, "unknown");
    }
    fclose(f);
}

static int run_diagnostics(void)
{
    struct utsname uts;
    char product_name[128];
    char board_name[128];
    int acpi_clv1_exists = 0;
    int dev_exists = 0;

    int fd;
    char diag_buf[512] = {0};

    printf("========================================\n");
    printf("  Acer ALG RGB Driver Diagnostic Report \n");
    printf("========================================\n\n");

    /* 1. Host & Hardware Info */
    read_sysfs_string("/sys/class/dmi/id/product_name", product_name, sizeof(product_name));
    read_sysfs_string("/sys/class/dmi/id/board_name", board_name, sizeof(board_name));

    printf("[*] Hardware:\n");
    printf("    Product Name:   %s\n", product_name);
    printf("    Board Name:     %s\n", board_name);

    if (uname(&uts) == 0) {
        printf("    Kernel Version: %s (%s)\n", uts.release, uts.machine);
    }

    printf("\n[*] CLI Utility:\n");
    printf("    CLI Version:    %s\n", ALG_RGB_VERSION_STRING);

    /* 2. ACPI Device Presence */
    printf("\n[*] ACPI Namespace:\n");
    if (access("/sys/bus/acpi/devices/CLV0001:00", F_OK) == 0) {
        printf("    CLV0001:00 (\\_SB.DCHU): PRESENT (Status: ");
        char status[16];
        read_sysfs_string("/sys/bus/acpi/devices/CLV0001:00/status", status, sizeof(status));
        printf("%s)\n", status);
        acpi_clv1_exists = 1;
    } else {
        printf("    CLV0001:00 (\\_SB.DCHU): NOT FOUND\n");
    }

    if (access("/sys/bus/acpi/devices/CLV0002:00", F_OK) == 0) {
        printf("    CLV0002:00 (\\_SB.DCHP): PRESENT\n");
    } else {
        printf("    CLV0002:00 (\\_SB.DCHP): NOT FOUND\n");
    }


    /* 3. Kernel Driver & Device Node */
    printf("\n[*] Kernel Driver & Device Node:\n");
    if (access("/sys/module/alg_rgb", F_OK) == 0) {
        printf("    Kernel Module:  alg_rgb is LOADED\n");
    } else {
        printf("    Kernel Module:  alg_rgb is NOT LOADED (try: sudo modprobe alg_rgb)\n");
    }

    if (access("/dev/alg_rgb", F_OK) == 0) {
        printf("    Device Node:    /dev/alg_rgb EXISTS\n");
        dev_exists = 1;
    } else {
        printf("    Device Node:    /dev/alg_rgb NOT FOUND\n");
    }

    /* 4. Read Diagnostic Block from Driver */
    if (dev_exists) {
        fd = open("/dev/alg_rgb", O_RDONLY);
        if (fd < 0) {
            printf("    Device Access:  FAILED (%s)\n", strerror(errno));
            if (errno == EACCES) {
                printf("    Hint: Ensure your user is in the 'alg-rgb' group: sudo usermod -aG alg-rgb $USER\n");
            }
        } else {
            ssize_t n = read(fd, diag_buf, sizeof(diag_buf) - 1);
            if (n > 0) {
                diag_buf[n] = '\0';
                printf("    Driver Diagnostic Data:\n");
                char *line = strtok(diag_buf, "\n");
                while (line) {
                    printf("      %s\n", line);
                    line = strtok(NULL, "\n");
                }
            } else {
                printf("    Driver Status:  read returned %zd (empty)\n", n);
            }
            close(fd);
        }
    }

    printf("\n[*] Diagnostic Summary:\n");
    if (acpi_clv1_exists && dev_exists) {
        printf("    [PASS] ACPI interface and kernel driver device node are available.\n");
        printf("    Note: Hardware LED illumination must be physically confirmed.\n");
    } else {
        printf("    [FAIL] Required interface or driver is missing. Review issues above.\n");
    }
    printf("========================================\n");

    return (acpi_clv1_exists && dev_exists) ? 0 : 1;
}

static const char *valid_colors[] = {
    "off", "red", "orange", "yellow", "lime", "light-green",
    "green", "green-cyan", "cyan", "light-blue", "blue", "violet",
    "magenta", "pink", "flesh", "bluish-white", "white"
};

static int is_valid_color(const char *c)
{
    size_t i;
    for (i = 0; i < sizeof(valid_colors) / sizeof(valid_colors[0]); i++) {
        if (!strcmp(c, valid_colors[i]))
            return 1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    int fd;
    char buffer[64];
    int brightness = 4;
    ssize_t ret;

    if (argc == 2) {
        if (!strcmp(argv[1], "--version")) {
            print_version();
            return 0;
        }

        if (!strcmp(argv[1], "--help") || !strcmp(argv[1], "-h")) {
            usage(argv[0]);
            return 0;
        }

        if (!strcmp(argv[1], "--diag") || !strcmp(argv[1], "-d")) {
            return run_diagnostics();
        }
    }

    if (argc != 2 && argc != 3) {
        usage(argv[0]);
        return 1;
    }

    if (!is_valid_color(argv[1])) {
        fprintf(stderr, "Error: Unknown color '%s'\n", argv[1]);
        fprintf(stderr, "Run '%s --help' to see supported colors.\n", argv[0]);
        return 1;
    }

    if (argc == 3) {
        char *endptr;
        brightness = (int)strtol(argv[2], &endptr, 10);
        if (*endptr != '\0' || brightness < 0 || brightness > 4) {
            fprintf(stderr, "Error: Brightness must be an integer between 0 and 4 (received '%s')\n", argv[2]);
            return 1;
        }
    }

    snprintf(buffer, sizeof(buffer), "%s %d", argv[1], brightness);

    fd = open("/dev/alg_rgb", O_WRONLY);
    if (fd < 0) {
        if (errno == ENOENT) {
            fprintf(stderr, "Error: /dev/alg_rgb does not exist.\n");
            fprintf(stderr, "Is the 'alg_rgb' module loaded? Try: sudo modprobe alg_rgb\n");
        } else if (errno == EACCES) {
            fprintf(stderr, "Error: Permission denied opening /dev/alg_rgb.\n");
            fprintf(stderr, "Ensure your user is in the 'alg-rgb' group: sudo usermod -aG alg-rgb $USER\n");
        } else {
            perror("Error opening /dev/alg_rgb");
        }
        return 1;
    }

    ret = write(fd, buffer, strlen(buffer));
    if (ret < 0) {
        if (errno == EOPNOTSUPP) {
            fprintf(stderr, "Error: ACPI _DSM returned unsupported (0x80000002). Firmware rejected this function.\n");
        } else if (errno == EPROTO) {
            fprintf(stderr, "Error: ACPI _DSM returned unexpected status from firmware.\n");
        } else if (errno == EBADMSG) {
            fprintf(stderr, "Error: ACPI _DSM returned unexpected non-integer object.\n");
        } else if (errno == EIO) {
            fprintf(stderr, "Error: ACPI execution failed in kernel (returned NULL). Check 'journalctl -k' for ACPI details.\n");
        } else if (errno == EINVAL) {
            fprintf(stderr, "Error: Kernel driver rejected command '%s' (invalid arguments or format).\n", buffer);
        } else {
            perror("Error writing to /dev/alg_rgb");
        }
        close(fd);
        return 1;
    }

    close(fd);
    printf("ACPI command delivered: color '%s', brightness %d (verify physical keyboard illumination)\n", argv[1], brightness);
    return 0;

}
