@echo off
rem Runs job.cmd inside the logged-on desktop session (session 2), not session 0.
rem Launched by the scheduled task "ttjob", created with /IT so it inherits the interactive
rem session. SSH cannot do this: sshd hands out session 0, which has no window station, so Qt
rem falls back to a font database that needs a font directory and the real windows plugin
rem cannot even set DPI awareness.
rem
rem `cmd /c`, not `call` (WIN-R2). A bare `exit` inside a *called* batch file exits the whole
rem cmd process - so a job command ending in `exit 0` terminated this script before it wrote
rem the done marker, and the caller waited out its full timeout on a command that had already
rem succeeded. A child cmd confines `exit` to itself and still yields its code.
rem A run in flight holds job.out open through the redirect below, so a second one cannot
rem write it and fails with "used by another process" - silently, from the caller's side.
rem This marker lets the caller refuse to start rather than collide (WIN-R2).
if exist C:\dev\interactive\job.done del C:\dev\interactive\job.done
>C:\dev\interactive\job.running echo running
cmd /c C:\dev\interactive\job.cmd > C:\dev\interactive\job.out 2>&1
rem Redirection written *first*, deliberately. `echo EXITCODE=%ERRORLEVEL%>>file` makes cmd
rem read the digit before `>>` as a stream handle - `EXITCODE=0>>` redirects handle 0 and the
rem line is never written, so the caller sees no result at all.
>>C:\dev\interactive\job.out echo EXITCODE=%ERRORLEVEL%
del C:\dev\interactive\job.running 2>nul
>C:\dev\interactive\job.done echo done
