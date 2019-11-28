This repository contains the sources, resources, and documentation
of the BlackBox Component Builder and a scripting tool that allows one
to run BlackBox commands from the command line.
A scripting tool is necessary for the CI (continues integration)
process used for BlackBox development.
For details of the build process see appbuild/build.py.


The general purpose BlackBox scripting tool bbscript.exe is based
on the scripting engine introduced in subsystem Script, which is
not part of the generated BlackBox distribution.


For compiling and linking the BlackBox Component Builder from sources:

  1. Download last version of the compiler:

    http://blackboxframework.org/makeapp/bbscript.exe

  2. Prepare 'Win/Rsrc/BlackBox.res' file
    
    Open and put version information to 'Win/Rsrc/BlackBox.rc'

    Compile this file:

    - Example for Windows:
        1) Download and install MinGW: http://www.mingw.org/
        2) C:\MinGW\bin>windres.exe -i C:\bbcb\Win\Rsrc\BlackBox.rc -o C:\bbcb\Win\Rsrc\BlackBox.res

    - Example for Linux Ubuntu:
        1) sudo apt-get install mingw32
        2) Go to the directory with sources
        3) /usr/bin/i586-mingw32msvc-windres -i BlackBox.rc -o BlackBox.res
    
  3. Run compiler:

    bbscript.exe /PAR Dev/Docu/Build-Tool.odc


For building a new bbscript.exe:

    bbscript.exe /PAR appbuild/newbbscript.txt

    or

    1. Add the 'Script' folder to your BlackBox directory
    2. Execute all commands from appbuild/newbbscript.txt
