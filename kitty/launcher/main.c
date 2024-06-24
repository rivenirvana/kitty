/*
 * launcher.c
 * Copyright (C) 2017 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#include <libgen.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#include <sys/syslimits.h>
#include <sys/stat.h>
#else
#include <limits.h>
#endif
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#include <Python.h>
#include <fcntl.h>
#include "launcher.h"

#ifndef KITTY_LIB_PATH
#define KITTY_LIB_PATH "../.."
#endif
#ifndef KITTY_LIB_DIR_NAME
#define KITTY_LIB_DIR_NAME "lib"
#endif

static void cleanup_free(void *p) { free(*(void**) p); }
#define RAII_ALLOC(type, name, initializer) __attribute__((cleanup(cleanup_free))) type *name = initializer


#ifndef __FreeBSD__
static bool
safe_realpath(const char* src, char *buf, size_t buf_sz) {
    RAII_ALLOC(char, ans, realpath(src, NULL));
    if (ans == NULL) return false;
    snprintf(buf, buf_sz, "%s", ans);
    return true;
}
#endif

typedef struct {
    const char *exe, *exe_dir, *lc_ctype, *lib_dir;
    char **argv;
    int argc;
} RunData;

static bool
set_kitty_run_data(RunData *run_data, bool from_source, wchar_t *extensions_dir) {
    PyObject *ans = PyDict_New();
    if (!ans) { PyErr_Print(); return false; }
    PyObject *exe_dir = PyUnicode_DecodeFSDefaultAndSize(run_data->exe_dir, strlen(run_data->exe_dir));
    if (exe_dir == NULL) { fprintf(stderr, "Fatal error: cannot decode exe_dir: %s\n", run_data->exe_dir); PyErr_Print(); Py_CLEAR(ans); return false; }
#define S(key, val) { if (!val) { PyErr_Print(); Py_CLEAR(ans); return false; } int ret = PyDict_SetItemString(ans, #key, val); Py_CLEAR(val); if (ret != 0) { PyErr_Print(); Py_CLEAR(ans); return false; } }
    S(bundle_exe_dir, exe_dir);
    if (from_source) {
        PyObject *one = Py_True; Py_INCREF(one);
        S(from_source, one);
    }
    if (run_data->lc_ctype) {
        PyObject *ctype = PyUnicode_DecodeLocaleAndSize(run_data->lc_ctype, strlen(run_data->lc_ctype), NULL);
        S(lc_ctype_before_python, ctype);
    }
    if (extensions_dir) {
        PyObject *ed = PyUnicode_FromWideChar(extensions_dir, -1);
        S(extensions_dir, ed);
    }
#undef S
    int ret = PySys_SetObject("kitty_run_data", ans);
    Py_CLEAR(ans);
    if (ret != 0) { PyErr_Print(); return false; }
    return true;
}


#ifdef FOR_BUNDLE
#include <bypy-freeze.h>

static bool
canonicalize_path(const char *srcpath, char *dstpath, size_t sz) {
    // remove . and .. path segments
    bool ok = false;
    size_t plen = strlen(srcpath) + 1, chk;
    RAII_ALLOC(char, wtmp, malloc(plen));
    RAII_ALLOC(char*, tokv, malloc(sizeof(char*) * plen));
    if (!wtmp || !tokv) goto end;
    char *s, *tok, *sav;
    bool relpath = *srcpath != '/';

    // use a buffer as strtok modifies its input
    memcpy(wtmp, srcpath, plen);

    tok = strtok_r(wtmp, "/", &sav);
    int ti = 0;
    while (tok != NULL) {
        if (strcmp(tok, "..") == 0) {
            if (ti > 0) ti--;
        } else if (strcmp(tok, ".") != 0) {
            tokv[ti++] = tok;
        }
        tok = strtok_r(NULL, "/", &sav);
    }

    chk = 0;
    s = dstpath;
    for (int i = 0; i < ti; i++) {
        size_t token_sz = strlen(tokv[i]);

        if (i > 0 || !relpath) {
            if (++chk >= sz) goto end;
            *s++ = '/';
        }

        chk += token_sz;
        if (chk >= sz) goto end;

        memcpy(s, tokv[i], token_sz);
        s += token_sz;
    }

    if (s == dstpath) {
        if (++chk >= sz) goto end;
        *s++ = relpath ? '.' : '/';
    }
    *s = '\0';
    ok = true;

end:
    return ok;
}

static bool
canonicalize_path_wide(const char *srcpath, wchar_t *dest, size_t sz) {
    char buf[sz + 1];
    bool ret = canonicalize_path(srcpath, buf, sz);
    buf[sz] = 0;
    mbstowcs(dest, buf, sz - 1);
    dest[sz-1] = 0;
    return ret;
}

static int
run_embedded(RunData *run_data) {
    bypy_pre_initialize_interpreter(false);
    char extensions_dir_full[PATH_MAX+1] = {0}, python_home_full[PATH_MAX+1] = {0};
#ifdef __APPLE__
    const char *python_relpath = "../Resources/Python/lib";
#else
    const char *python_relpath = "../" KITTY_LIB_DIR_NAME;
#endif
    int num = snprintf(extensions_dir_full, PATH_MAX, "%s/%s/kitty-extensions", run_data->exe_dir, python_relpath);
    if (num < 0 || num >= PATH_MAX) { fprintf(stderr, "Failed to create path to extensions_dir: %s/%s\n", run_data->exe_dir, python_relpath); return 1; }
    wchar_t extensions_dir[num+2];
    if (!canonicalize_path_wide(extensions_dir_full, extensions_dir, num+1)) {
        fprintf(stderr, "Failed to canonicalize the path: %s\n", extensions_dir_full); return 1; }

    num = snprintf(python_home_full, PATH_MAX, "%s/%s/python%s", run_data->exe_dir, python_relpath, PYVER);
    if (num < 0 || num >= PATH_MAX) { fprintf(stderr, "Failed to create path to python home: %s/%s\n", run_data->exe_dir, python_relpath); return 1; }
    wchar_t python_home[num+2];
    if (!canonicalize_path_wide(python_home_full, python_home, num+1)) {
        fprintf(stderr, "Failed to canonicalize the path: %s\n", python_home_full); return 1; }

    bypy_initialize_interpreter(
            L"kitty", python_home, L"kitty_main", extensions_dir, run_data->argc, run_data->argv);
    if (!set_kitty_run_data(run_data, false, extensions_dir)) return 1;
    set_sys_bool("frozen", true);
    return bypy_run_interpreter();
}

#else

static int
run_embedded(RunData *run_data) {
    bool from_source = false;
#ifdef FROM_SOURCE
    from_source = true;
#endif
    PyStatus status;
    PyPreConfig preconfig;
    PyPreConfig_InitPythonConfig(&preconfig);
    preconfig.utf8_mode = 1;
    preconfig.coerce_c_locale = 1;
#ifdef SET_PYTHON_HOME
    preconfig.isolated = 1;
#endif
    status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) goto fail;
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.parse_argv = 0;
    config.optimization_level = 2;
    status = PyConfig_SetBytesArgv(&config, run_data->argc, run_data->argv);
    if (PyStatus_Exception(status)) goto fail;
    status = PyConfig_SetBytesString(&config, &config.executable, run_data->exe);
    if (PyStatus_Exception(status)) goto fail;
    status = PyConfig_SetBytesString(&config, &config.run_filename, run_data->lib_dir);
    if (PyStatus_Exception(status)) goto fail;
#ifdef SET_PYTHON_HOME
#ifndef __APPLE__
    char pyhome[256];
    snprintf(pyhome, sizeof(pyhome), "%s/%s", run_data->lib_dir, SET_PYTHON_HOME);
    status = PyConfig_SetBytesString(&config, &config.home, pyhome);
    if (PyStatus_Exception(status)) goto fail;
#endif
    config.isolated = 1;
#endif
    status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status))  goto fail;
    PyConfig_Clear(&config);
    if (!set_kitty_run_data(run_data, from_source, NULL)) return 1;
    PySys_SetObject("frozen", Py_False);
    return Py_RunMain();
fail:
    PyConfig_Clear(&config);
    if (PyStatus_IsExit(status)) return status.exitcode;
    Py_ExitStatusException(status);
}

#endif

// read_exe_path() {{{
#ifdef __APPLE__
static bool
read_exe_path(char *exe, size_t buf_sz) {
    (void)buf_sz;
    uint32_t size = PATH_MAX;
    char apple[PATH_MAX+1] = {0};
    if (_NSGetExecutablePath(apple, &size) != 0) { fprintf(stderr, "Failed to get path to executable\n"); return false; }
    if (!safe_realpath(apple, exe, buf_sz)) { fprintf(stderr, "realpath() failed on the executable's path\n"); return false; }
    return true;
}
#elif defined(__FreeBSD__)
#include <sys/param.h>
#include <sys/sysctl.h>

static bool
read_exe_path(char *exe, size_t buf_sz) {
    int name[] = { CTL_KERN, KERN_PROC, KERN_PROC_PATHNAME, -1 };
    size_t length = buf_sz;
    int error = sysctl(name, 4, exe, &length, NULL, 0);
    if (error < 0 || length <= 1) {
        fprintf(stderr, "failed to get path to executable, sysctl() failed\n");
        return false;
    }
    return true;
}
#elif defined(__NetBSD__)

static bool
read_exe_path(char *exe, size_t buf_sz) {
    if (!safe_realpath("/proc/curproc/exe", exe, buf_sz)) { fprintf(stderr, "Failed to read /proc/curproc/exe\n"); return false; }
    return true;
}

#elif defined(__OpenBSD__)
static bool
read_exe_path(char *exe, size_t buf_sz) {
    const char *path = getenv("PATH");
    if (!path) { fprintf(stderr, "No PATH environment variable set, aborting\n"); return false; }
    char buf[PATH_MAX + 1] = {0};
    strncpy(buf, path, PATH_MAX);
    char *token = strtok(buf, ":");
    while (token != NULL) {
        char q[PATH_MAX + 1] = {0};
        snprintf(q, PATH_MAX, "%s/kitty", token);
        if (safe_realpath(q, exe, buf_sz)) return true;
        token = strtok(NULL, ":");
    }
    fprintf(stderr, "kitty not found in PATH aborting\n");
    return false;
}

#else

static bool
read_exe_path(char *exe, size_t buf_sz) {
    if (!safe_realpath("/proc/self/exe", exe, buf_sz)) { fprintf(stderr, "Failed to read /proc/self/exe\n"); return false; }
    return true;
}
#endif // }}}

static bool
is_valid_fd(int fd)
{
    // This is copied from the python source code as we need the exact same semantics
    // to prevent python from giving us None for sys.stdout and friends.
#if defined(F_GETFD) && ( \
        defined(__linux__) || \
        defined(__APPLE__) || \
        defined(__wasm__))
    return fcntl(fd, F_GETFD) >= 0;
#elif defined(__linux__)
    int fd2 = dup(fd);
    if (fd2 >= 0) {
        close(fd2);
    }
    return (fd2 >= 0);
#else
    struct stat st;
    return (fstat(fd, &st) == 0);
#endif
}

static bool
reopen_to_null(const char *mode, FILE *stream) {
    errno = 0;
    while (true) {
        if (freopen("/dev/null", mode, stream) != NULL) return true;
        if (errno == EINTR) continue;
        perror("Failed to re-open STDIO handle to /dev/null");
        return false;
    }
}

static bool
ensure_working_stdio(void) {
#define C(which, mode) { \
    int fd = fileno(which); \
    if (fd < 0) { if (!reopen_to_null(mode, which)) return false; } \
    else if (!is_valid_fd(fd)) { \
        close(fd); if (!reopen_to_null(mode, which)) return false; \
    }}
    C(stdin, "r") C(stdout, "w") C(stderr, "w")
    return true;
#undef C
}

static bool
is_wrapped_kitten(const char *arg) {
    char buf[64];
    snprintf(buf, sizeof(buf)-1, " %s ", arg);
    return strstr(" " WRAPPED_KITTENS " ", buf);
}

static void
exec_kitten(int argc, char *argv[], char *exe_dir) {
    char exe[PATH_MAX+1] = {0};
    snprintf(exe, PATH_MAX, "%s/kitten", exe_dir);
    char **newargv = malloc(sizeof(char*) * (argc + 1));
    memcpy(newargv, argv, sizeof(char*) * argc);
    newargv[argc] = 0;
    newargv[0] = "kitten";
    errno = 0;
    execv(exe, newargv);
    fprintf(stderr, "Failed to execute kitten (%s) with error: %s\n", exe, strerror(errno));
    exit(1);
}

static void
delegate_to_kitten_if_possible(int argc, char *argv[], char* exe_dir) {
    if (argc > 1 && argv[1][0] == '@') exec_kitten(argc, argv, exe_dir);
    if (argc > 2 && strcmp(argv[1], "+kitten") == 0 && is_wrapped_kitten(argv[2])) exec_kitten(argc - 1, argv + 1, exe_dir);
    if (argc > 3 && strcmp(argv[1], "+") == 0 && strcmp(argv[2], "kitten") == 0 && is_wrapped_kitten(argv[3])) exec_kitten(argc - 2, argv + 2, exe_dir);
}

static bool
is_boolean_flag(const char *x) {
    static const char *all_boolean_options = KITTY_CLI_BOOL_OPTIONS;
    char buf[128];
    snprintf(buf, sizeof(buf), " %s ", x);
    return strstr(all_boolean_options, buf) != NULL;
}

static void
handle_fast_commandline(int argc, char *argv[]) {
    char current_option_expecting_argument[128] = {0};
    CLIOptions opts = {0};
    int first_arg = 1;
    if (argc > 1 && strcmp(argv[1], "+open") == 0) {
        first_arg = 2;
    } else if (argc > 2 && strcmp(argv[1], "+") == 0 && strcmp(argv[2], "open") == 0) {
        first_arg = 3;
    }
    for (int i = first_arg; i < argc; i++) {
        const char *arg = argv[i];
        if (current_option_expecting_argument[0]) {
handle_option_value:
            if (strcmp(current_option_expecting_argument, "session") == 0) {
                opts.session = arg;
            } else if (strcmp(current_option_expecting_argument, "instance-group") == 0) {
                opts.instance_group = arg;
            }
            current_option_expecting_argument[0] = 0;
        } else {
            if (!arg || !arg[0] || !arg[1] || arg[0] != '-' || strcmp(arg, "--") == 0) {
                if (first_arg > 1) {
                    opts.open_urls = argv + i;
                    opts.open_url_count = argc - i;
                }
                break;
            }
            if (arg[1] == '-') {  // long opt
                const char *equal = strchr(arg, '=');
                if (equal == NULL) {
                    if (strcmp(arg+2, "version") == 0) {
                        opts.version_requested = true;
                    } else if (strcmp(arg+2, "single-instance") == 0) {
                        opts.single_instance = true;
                    } else if (strcmp(arg+2, "wait-for-single-instance-window-close") == 0) {
                        opts.wait_for_single_instance_window_close = true;
                    } else if (!is_boolean_flag(arg+2)) {
                        strncpy(current_option_expecting_argument, arg+2, sizeof(current_option_expecting_argument)-1);
                    }
                } else {
                    memcpy(current_option_expecting_argument, arg+2, equal - (arg + 2));
                    arg = equal + 1;
                    goto handle_option_value;
                }
            } else {
                char buf[2] = {0};
                for (int i = 1; arg[i] != 0; i++) {
                    switch(arg[i]) {
                        case 'v': opts.version_requested = true; break;
                        case '1': opts.single_instance = true; break;
                        default:
                            buf[0] = arg[i]; buf[1] = 0;
                            if (!is_boolean_flag(buf)) { current_option_expecting_argument[0] = arg[i]; current_option_expecting_argument[1] = 0; }
                    }
                }
            }
        }
    }

    if (opts.version_requested) {
        if (isatty(STDOUT_FILENO)) {
            printf("\x1b[3mkitty\x1b[23m \x1b[32m%s\x1b[39m created by \x1b[1;34mKovid Goyal\x1b[22;39m\n", KITTY_VERSION);
        } else {
            printf("kitty %s created by Kovid Goyal\n", KITTY_VERSION);
        }
        exit(0);
    }
    if (opts.single_instance) single_instance_main(argc, argv, &opts);
}

int main(int argc, char *argv[], char* envp[]) {
    if (argc < 1 || !argv) { fprintf(stderr, "Invalid argc/argv\n"); return 1; }
    if (!ensure_working_stdio()) return 1;
    char exe[PATH_MAX+1] = {0};
    char exe_dir_buf[PATH_MAX+1] = {0};
    RAII_ALLOC(const char, lc_ctype, NULL);
#ifdef __APPLE__
    lc_ctype = getenv("LC_CTYPE");
    if (lc_ctype) lc_ctype = strdup(lc_ctype);
#endif
    if (!read_exe_path(exe, sizeof(exe))) return 1;
    strncpy(exe_dir_buf, exe, sizeof(exe_dir_buf));
    char *exe_dir = dirname(exe_dir_buf);
    delegate_to_kitten_if_possible(argc, argv, exe_dir);
    handle_fast_commandline(argc, argv);
    int num, ret=0;
    char lib[PATH_MAX+1] = {0};
    if (KITTY_LIB_PATH[0] == '/') {
        num = snprintf(lib, PATH_MAX, "%s", KITTY_LIB_PATH);
    } else {
        num = snprintf(lib, PATH_MAX, "%s/%s", exe_dir, KITTY_LIB_PATH);
    }

    if (num < 0 || num >= PATH_MAX) { fprintf(stderr, "Failed to create path to kitty lib\n"); return 1; }
    RunData run_data = {.exe = exe, .exe_dir = exe_dir, .lib_dir = lib, .argc = argc, .argv = argv, .lc_ctype = lc_ctype};
    ret = run_embedded(&run_data);
    return ret;
}
