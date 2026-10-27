// SPDX-License-Identifier: GPL-2.0
/*
 * alg-fan.c
 *
 * Acer ALG AL15G-52 Fan Control Utility
 * Controls dual fans (CPU Fan 1 & GPU Fan 2) via /dev/alg_fan.
 */

#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/utsname.h>

#include "../include/version.h"

#define FAN_DEV_PATH "/dev/alg_fan"

static void print_version(void)
{
    printf("alg-fan %s\n", ALG_RGB_VERSION_STRING);
}

static void usage(const char *prog)
{
    printf("Acer ALG Fan Controller (v%s)\n\n", ALG_RGB_VERSION_STRING);
    printf("Usage:\n");
    printf("  %s auto                         Restore firmware automatic closed loop (SCMD 0x69)\n", prog);
    printf("  %s <duty_pct>                   Set both CPU and GPU fans to duty percentage (25-100)\n", prog);
    printf("  %s <cpu_duty> <gpu_duty>        Set independent CPU Fan 1 & GPU Fan 2 duty (25-100)\n", prog);
    printf("  %s -d, --diag, --status         Display fan hardware and driver diagnostic report\n\n", prog);
    printf("Examples:\n");
    printf("  %s auto\n", prog);
    printf("  %s 50\n", prog);
    printf("  %s 40 60\n", prog);
    printf("  %s 100 100\n\n", prog);
    printf("Safety Note:\n");
    printf("  Minimum duty is clamped to 25%% (raw 64) in firmware to prevent fan stall.\n");
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
    int fd;
    char diag_buf[512] = {0};

    printf("========================================\n");
    printf("  Acer ALG Fan Driver Diagnostic Report \n");
    printf("========================================\n\n");

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

    printf("\n[*] Kernel Driver & Device Node:\n");
    if (access("/sys/module/alg_rgb", F_OK) == 0) {
        printf("    Kernel Module:  alg_rgb is LOADED\n");
    } else {
        printf("    Kernel Module:  alg_rgb is NOT LOADED (try: sudo modprobe alg_rgb)\n");
    }

    if (access(FAN_DEV_PATH, F_OK) == 0) {
        printf("    Device Node:    " FAN_DEV_PATH " EXISTS\n");
        fd = open(FAN_DEV_PATH, O_RDONLY);
        if (fd < 0) {
            printf("    Device Access:  FAILED (%s)\n", strerror(errno));
            if (errno == EACCES) {
                printf("    Hint: Ensure your user is in the 'alg-rgb' group: sudo usermod -aG alg-rgb $USER\n");
            }
        } else {
            ssize_t n = read(fd, diag_buf, sizeof(diag_buf) - 1);
            if (n > 0) {
                diag_buf[n] = '\0';
                printf("    Fan Diagnostic Data:\n");
                char *line = strtok(diag_buf, "\n");
                while (line) {
                    printf("      %s\n", line);
                    line = strtok(NULL, "\n");
                }
            }
            close(fd);
        }
    } else {
        printf("    Device Node:    " FAN_DEV_PATH " NOT FOUND\n");
        printf("    Hint: Install or reload updated kernel module with sudo ./install.sh\n");
    }

    printf("========================================\n");
    return 0;
}

int main(int argc, char **argv)
{
    int fd;
    char cmd_buf[64];
    int cpu_pct = 50;
    int gpu_pct = 50;
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
        if (!strcmp(argv[1], "--diag") || !strcmp(argv[1], "-d") || !strcmp(argv[1], "--status")) {
            return run_diagnostics();
        }
        if (!strcmp(argv[1], "auto") || !strcmp(argv[1], "restore") || !strcmp(argv[1], "reset")) {
            snprintf(cmd_buf, sizeof(cmd_buf), "auto");
            goto send_command;
        }

        /* Single number -> apply to both CPU and GPU */
        char *endptr;
        cpu_pct = (int)strtol(argv[1], &endptr, 10);
        if (*endptr == '\0' && cpu_pct >= 0 && cpu_pct <= 100) {
            gpu_pct = cpu_pct;
            snprintf(cmd_buf, sizeof(cmd_buf), "%d %d", cpu_pct, gpu_pct);
            goto send_command;
        }
    } else if (argc == 3) {
        if (!strcmp(argv[1], "set") || !strcmp(argv[1], "manual")) {
            char *endptr;
            cpu_pct = (int)strtol(argv[2], &endptr, 10);
            gpu_pct = cpu_pct;
            snprintf(cmd_buf, sizeof(cmd_buf), "%d %d", cpu_pct, gpu_pct);
            goto send_command;
        }

        char *end1, *end2;
        cpu_pct = (int)strtol(argv[1], &end1, 10);
        gpu_pct = (int)strtol(argv[2], &end2, 10);
        if (*end1 == '\0' && *end2 == '\0' && cpu_pct >= 0 && cpu_pct <= 100 && gpu_pct >= 0 && gpu_pct <= 100) {
            snprintf(cmd_buf, sizeof(cmd_buf), "%d %d", cpu_pct, gpu_pct);
            goto send_command;
        }
    } else if (argc == 4) {
        if (!strcmp(argv[1], "set") || !strcmp(argv[1], "manual")) {
            char *end1, *end2;
            cpu_pct = (int)strtol(argv[2], &end1, 10);
            gpu_pct = (int)strtol(argv[3], &end2, 10);
            if (*end1 == '\0' && *end2 == '\0' && cpu_pct >= 0 && cpu_pct <= 100 && gpu_pct >= 0 && gpu_pct <= 100) {
                snprintf(cmd_buf, sizeof(cmd_buf), "%d %d", cpu_pct, gpu_pct);
                goto send_command;
            }
        }
    }

    usage(argv[0]);
    return 1;

send_command:
    fd = open(FAN_DEV_PATH, O_WRONLY);
    if (fd < 0) {
        if (errno == ENOENT) {
            fprintf(stderr, "Error: " FAN_DEV_PATH " does not exist.\n");
            fprintf(stderr, "Is the updated 'alg_rgb' module loaded? Try: sudo ./install.sh\n");
        } else if (errno == EACCES) {
            fprintf(stderr, "Error: Permission denied opening " FAN_DEV_PATH ".\n");
            fprintf(stderr, "Ensure your user is in the 'alg-rgb' group: sudo usermod -aG alg-rgb $USER\n");
        } else {
            perror("Error opening " FAN_DEV_PATH);
        }
        return 1;
    }

    ret = write(fd, cmd_buf, strlen(cmd_buf));
    if (ret < 0) {
        perror("Error writing to " FAN_DEV_PATH);
        close(fd);
        return 1;
    }

    close(fd);
    if (!strcmp(cmd_buf, "auto")) {
        printf("ACPI command delivered: Restored firmware automatic fan control (SCMD 0x69)\n");
    } else {
        printf("ACPI command delivered: CPU Fan 1 = %d%%, GPU Fan 2 = %d%% (SCMD 0x68)\n", cpu_pct, gpu_pct);
    }
    return 0;
}
