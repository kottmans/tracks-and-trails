@echo off
rem Runs job.cmd inside the logged-on desktop session (session 2), not session 0.
rem Launched by the scheduled task "ttjob", which is created with /IT so it inherits the
rem interactive session. SSH cannot do this: sshd hands out session 0, which has no window
rem station, so Qt falls back to a font database that needs a font directory and the real
rem windows plugin cannot even set DPI awareness.
if exist C:\dev\interactive\job.done del C:\dev\interactive\job.done
call C:\dev\interactive\job.cmd > C:\dev\interactive\job.out 2>&1
echo EXITCODE=%ERRORLEVEL%>> C:\dev\interactive\job.out
echo done> C:\dev\interactive\job.done
