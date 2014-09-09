This repository contains the sources for the BlackBox Component Builder
and the command line compiler(s). A command line compiler is necessary for the CI
(continues integration) process used for BlackBox development.
For details of the build process see appbuild/build*.py.


The general purpose BlackBox scripting tool bbscript.exe is based
on the scripting engine introduced in subsystem Script, which is 
not part of the generated BlackBox distribution.

For compiling the BlackBox Component Builder:

    bbscript.exe /PAR Dev/Docu/Build-Tool.odc

For building a new bbscript.exe:

    bbscript.exe /PAR appbuild/newbbscript.txt

    or

    1. Add 'Script' folder to your BlackBox directory
    2. Execute all commands from appbuild/newbbscript.txt


The command line compiler dev0 is based on a general purpose but limited
BlackBox scripting feature introduced in the directories Cons and Interp,
which are not part of the generated BlackBox distribution.


For compiling the BlackBox Component Builder:

    dev0.exe < appbuild/build.txt

For building a new dev0.exe:

    dev0.exe < appbuild/newdev0.txt

    or

    1. Add 'Cons' and 'Interp' folders to your BlackBox directory
    2. Execute all commanders from Interp/Docu/Quick-Start.odc
