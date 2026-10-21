// TryHardRed smoke runner core: a headless mGBA that takes simple commands on stdin, one per line.
// tools/smoke/smoke.py drives it (button presses, waits, memory reads, screenshots, save states).
//   frames N        run N frames with the current keys held
//   keys MASK       set the held keys (GBA key bits: A=1 B=2 SELECT=4 START=8 RIGHT=16 LEFT=32 UP=64 DOWN=128 R=256 L=512)
//   read8|read16|read32 ADDR   print the value at ADDR
//   dump ADDR LEN   print LEN bytes from ADDR as hex
//   write8|write16|write32 ADDR VALUE
//   shot PATH       write the screen as a PNG
//   save PATH | load PATH      save state to or from a file
//   quit
// Build: cc -O2 -DUSE_PNG -o smokecore smokecore.c -lmgba -lpng (libmgba-dev on Ubuntu/Debian).
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba-util/png-io.h>
#include <mgba-util/vfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>

static void QuietLog(struct mLogger *logger, int category, enum mLogLevel level, const char *format, va_list args)
{
}

int main(int argc, char **argv)
{
    static struct mLogger quiet = {.log = QuietLog};
    mLogSetDefaultLogger(&quiet);
    if (argc < 2)
    {
        fprintf(stderr, "usage: smokecore ROM\n");
        return 2;
    }
    struct mCore *core = mCoreFind(argv[1]);
    if (!core || !core->init(core))
    {
        fprintf(stderr, "smokecore: can't open %s\n", argv[1]);
        return 1;
    }
    mCoreInitConfig(core, NULL);
    unsigned width, height;
    core->desiredVideoDimensions(core, &width, &height);
    color_t *video = calloc(width * height, sizeof(*video));
    core->setVideoBuffer(core, video, width);
    if (!mCoreLoadFile(core, argv[1]))
    {
        fprintf(stderr, "smokecore: can't load %s\n", argv[1]);
        return 1;
    }
    core->reset(core);

    char line[1024];
    setvbuf(stdout, NULL, _IOLBF, 0);
    while (fgets(line, sizeof(line), stdin))
    {
        char cmd[32] = {0}, arg[1000] = {0};
        sscanf(line, "%31s %999[^\n]", cmd, arg);
        if (!strcmp(cmd, "frames"))
        {
            long n = strtol(arg, NULL, 0);
            for (long i = 0; i < n; i++)
                core->runFrame(core);
            printf("ok\n");
        }
        else if (!strcmp(cmd, "keys"))
        {
            core->setKeys(core, (uint32_t)strtoul(arg, NULL, 0));
            printf("ok\n");
        }
        else if (!strcmp(cmd, "read8"))
            printf("%u\n", core->busRead8(core, (uint32_t)strtoul(arg, NULL, 0)));
        else if (!strcmp(cmd, "read16"))
            printf("%u\n", core->busRead16(core, (uint32_t)strtoul(arg, NULL, 0)));
        else if (!strcmp(cmd, "read32"))
            printf("%u\n", core->busRead32(core, (uint32_t)strtoul(arg, NULL, 0)));
        else if (!strcmp(cmd, "dump"))
        {
            unsigned long addr = 0, len = 0;
            sscanf(arg, "%li %li", (long *)&addr, (long *)&len);
            for (unsigned long i = 0; i < len; i++)
                printf("%02x", core->busRead8(core, (uint32_t)(addr + i)));
            printf("\n");
        }
        else if (!strncmp(cmd, "write", 5))
        {
            unsigned long addr = 0, value = 0;
            sscanf(arg, "%li %li", (long *)&addr, (long *)&value);
            if (!strcmp(cmd, "write8"))
                core->busWrite8(core, (uint32_t)addr, (uint8_t)value);
            else if (!strcmp(cmd, "write16"))
                core->busWrite16(core, (uint32_t)addr, (uint16_t)value);
            else
                core->busWrite32(core, (uint32_t)addr, (uint32_t)value);
            printf("ok\n");
        }
        else if (!strcmp(cmd, "shot"))
        {
            struct VFile *vf = VFileOpen(arg, O_CREAT | O_TRUNC | O_WRONLY);
            bool ok = false;
            if (vf)
            {
                png_structp png = PNGWriteOpen(vf);
                png_infop info = PNGWriteHeader(png, width, height);
                ok = PNGWritePixels(png, width, height, width, video);
                PNGWriteClose(png, info);
                vf->close(vf);
            }
            printf(ok ? "ok\n" : "err\n");
        }
        else if (!strcmp(cmd, "save") || !strcmp(cmd, "load"))
        {
            bool save = !strcmp(cmd, "save");
            struct VFile *vf = VFileOpen(arg, save ? (O_CREAT | O_TRUNC | O_RDWR) : O_RDONLY);
            bool ok = vf && (save ? mCoreSaveStateNamed(core, vf, SAVESTATE_SAVEDATA | SAVESTATE_RTC)
                                  : mCoreLoadStateNamed(core, vf, SAVESTATE_SAVEDATA | SAVESTATE_RTC));
            if (vf)
                vf->close(vf);
            printf(ok ? "ok\n" : "err\n");
        }
        else if (!strcmp(cmd, "quit"))
            break;
        else
            printf("err unknown command\n");
    }
    core->deinit(core);
    free(video);
    return 0;
}
