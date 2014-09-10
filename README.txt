This repository contains the sources, resources, and documentation
of the BlackBox Component Builder and a scripting tool that allows one
to run BlackBox commands from the command line.
A scripting tool is necessary for the CI (continues integration) 
process used for BlackBox development.
For details of the build process see appbuild/build.py.


The general purpose BlackBox scripting tool bbscript.exe is based
on the scripting engine introduced in subsystem Script, which is 
not part of the generated BlackBox distribution.


For compiling and linking the BlackBox Component Builder:

    bbscript.exe /PAR Dev/Docu/Build-Tool.odc


For building a new bbscript.exe:

    bbscript.exe /PAR appbuild/newbbscript.txt

    or

    1. Add the 'Script' folder to your BlackBox directory
    2. Execute all commands from appbuild/newbbscript.txt
