#!/usr/bin/python
#
# Automated build of the BlackBox Component Builder for Windows under Linux Debian 7.
# Looks at all branches and puts the output into the branch's output folder 'unstable/<branch>'
# unless building a final release, which is always put into folder 'stable'.
#
# Ivan Denisov, Josef Templ
#
# use: "build.py -h" to get a short help text
#
# Creates 3 files in case of success:
# 1. a build log file named blackbox-<AppVersion>.<buildnr>-buildlog.html
# 2. a Windows installer file named blackbox-<AppVersion>.<buildnr>-setup.exe
# 3. a zipped package named blackbox-<AppVersion>-<buildnr>.zip
# In case of building a final release, buildnr is not included.
# In case building was started for a branch, updates the branch's last-build-commit hash.
# In case of successfully finishing the build, increments the global build number.
#
# By always rebuilding bbscript.exe it avoids problems with changes in the symbol or object file formats
# and acts as a rigorous test for some parts of BlackBox, in particular for the compiler itself.
# This script uses the general purpose 'bbscript' scripting engine for BlackBox, which
# can be found in the subsystem named 'Script'.
#
# Error handling:
# Stops building when shellExec writes to stderr, unless stopOnError is False.
# Stops building when there is an error reported by bbscript.
# Stops building when there is a Python exception.
# The next build will take place upon the next commit.
#
# TODO git checkout reports a message on stderr but it works, so it is ignored

from subprocess import Popen, PIPE, call
import sys, datetime, fileinput, os.path, argparse

buildDate = datetime.datetime.now().isoformat()[:19]
buildDir = "/var/www/tribiq/makeapp"
bbName = "bb"
bbDir = buildDir + "/" + bbName
appbuildDir = bbDir + "/appbuild"
localRepository = "/var/www/git/blackbox.git"
unstableDir = "/var/www/tribiq/unstable"
stableDir = "/var/www/tribiq/stable"
wine = "/usr/local/bin/wine"
bbscript = "export DISPLAY=:1 && " + wine + " bbscript.exe"
iscc = "/usr/local/bin/iscc"
windres="/usr/bin/i586-mingw32msvc-windres"
testName = "testbuild"
branch = None
commitHash = None
logFile = None

parser = argparse.ArgumentParser(description='Build BlackBox')
parser.add_argument('--verbose', action="store_true", default=False, help='turn verbose output on')
parser.add_argument('--test', action="store_true", default=False, help='put all results into local directory "' + testName + '"')
parser.add_argument('--branch', help='select BRANCH for building')
args = parser.parse_args()

def repositoryLocked():
    return os.path.exists(localRepository + ".lock")

def hashFilePath():
    return buildDir + "/lastBuildHash/" + branch

def getLastHash():
    if os.path.exists(hashFilePath()):
        hashFile = open(hashFilePath(), "r")
        commit = hashFile.readline().strip()
        hashFile.close()
        return commit
    else:
        return ""

def getCommitHash():
    gitLog = shellExec(localRepository, "git log " + branch + " -1")
    global commitHash
    commitHash = gitLog.split("\n")[0].split(" ")[1]
    return commitHash

def needsRebuild():
    return getLastHash() != getCommitHash()

def selectBranch():
    global branch
    if args.branch != None:
        branch = args.branch
        getCommitHash()
        return branch
    else:
        branches = shellExec(localRepository, "git branch -a")
        for line in branches.split("\n"):
            branch = line[2:].strip()
            if branch != "" and needsRebuild():
                return branch
        return None

def openLog():
    global logFile
    logFile = open(unstableDir + "/logFile.html", "w")

def logVerbose(text):
    if args.verbose:
        print text # for testing, goes to console

def log(text, startMarkup="", endMarkup=""):
    if text != "":
        if logFile != None:
            for line in text.split("\n"):
               logFile.write(startMarkup + line + endMarkup + "<br/>\n")
            logFile.flush()
        elif args.verbose:
            for line in text.split("\n"):
               logVerbose(line)

def logErr(text): # use color red
    log(text, '<font color="#FF0000">', '</font>')

def logStep(text): # use bold font
    log(text, '<b>', '</b>')

def logShell(text): # use color green
    log(text, '<font color="#009600">', '</font>')

def shellExec(wd, cmd, stopOnError=True):
    logShell("cd " + wd + " && " + cmd)
    (stdout, stderr) = Popen("cd " + wd + " && " + cmd, stdout=PIPE, stderr=PIPE, shell=True).communicate()
    log(stdout)
    if stderr == "":
        return stdout
    elif not stopOnError:
        logErr(stderr)
        logErr("--- error ignored ---")
        return stdout
    else:
        logErr(stderr)
        logErr("--- build aborted ---")
        print "--- build aborted ---"
        incrementBuildNumber() # if not args.test
        cleanup() # if not args.test
        renameLog() # if not args.test
        sys.exit()

def getAppVerName(appVersion):
    x = appVersion
    if appVersion.find("-a") >= 0:
        x = appVersion.replace("-a", " Alpha ")
    elif appVersion.find("-b") >= 0:
        x = appVersion.replace("-b", " Beta ")
    elif appVersion.find("-rc") >= 0:
        x = appVersion.replace("-rc", " Release Candidate ")
    return "BlackBox Component Builder " + x

def getVersionInfoVersion(appVersion, buildNum):
    version = appVersion.split("-")[0]
    v = version.split(".")
    v0 = v[0] if len(v) > 0 else "0"
    v1 = v[1] if len(v) > 1 else "0"
    v2 = v[2] if len(v) > 2 else "0"
    return v0 + "." + v1 + "." + v2 + "." + str(buildNum)

def isFinal(appVersion):
    return appVersion.find("-") < 0

def prepareCompileAndLink():
    logStep("Preparing BlackBox.rc")
    vrsn = versionInfoVersion.replace(".", ",")
    shellExec(bbDir + "/Win/Rsrc", "mv BlackBox.rc BlackBox.rc_template")
    shellExec(bbDir + "/Win/Rsrc", "sed s/{#VERSION}/" + vrsn + "/ < BlackBox.rc_template > BlackBox.rc")
    shellExec(bbDir + "/Win/Rsrc", "rm BlackBox.rc_template")
    logStep("Creating the BlackBox.res resource file")
    shellExec(bbDir + "/Win/Rsrc", windres + " -i BlackBox.rc -o BlackBox.res")
    logStep("Preparing bbscript.exe")
    shellExec(buildDir, "cp bbscript.exe " + bbDir + "/")
    logStep("Starting Xvfb")
    if os.path.exists("/tmp/.X1-lock"):
        log("Xvfb is already running: /tmp/.X1-lock exists")
    else:
        shellExec(buildDir, "Xvfb :1 &")

def deleteBbFile(name):
    if os.path.exists(bbDir + "/" + name):
        shellExec(bbDir, "rm " + name)

def runbbscript(fileName):
    deleteBbFile("StdLog.txt");
    # fileName is relative to bbscript.exe startup directory, which is bbDir
    # if a /USE param is useed it must an absolute path, otherwise some texts cannot be opened, e.g Converters.
    cmd = "cd " + bbDir + " && " + bbscript + ' /PAR "' + fileName + '"'
    logShell(cmd)
    bbres = call(cmd + " >wine_out.txt 2>&1", shell=True) # wine produces irrelevant error messages
    if bbres != 0:
        shellExec(bbDir, "cat StdLog.txt", False)
        cleanup()
        logErr("--- build aborted ---")
        renameLog() # if not args.test
        sys.exit()

def compileAndLink():
    logStep("Compiling and linking BlackBox")
    runbbscript("Dev/Docu/Build-Tool.odc")
    shellExec(bbDir, "mv BlackBox2.exe BlackBox.exe && mv Code System/ && mv Sym System/")

def buildBbscript():
    logStep("Incrementally building BlackBox scripting engine bbscript.exe")
    runbbscript("appbuild/newbbscript.txt")
    shellExec(bbDir, "mv newbbscript.exe bbscript.exe && chmod a+x bbscript.exe")
    shellExec(bbDir, "rm -R Code Sym */Code */Sym BlackBox.exe")

def appendSystemProperties():
    logStep("Setting system properties in appendProps.txt")
    shellExec(appbuildDir, 'sed s/{#AppVersion}/"' + appVersion + '"/ < appendProps.txt > appendProps_.txt')
    shellExec(appbuildDir, 'sed s/{#AppVerName}/"' + appVerName + '"/ < appendProps_.txt > appendProps.txt')
    shellExec(appbuildDir, "sed s/{#FileVersion}/" + versionInfoVersion + "/ < appendProps.txt > appendProps_.txt")
    shellExec(appbuildDir, "sed s/{#BuildNum}/" + str(buildNum) + "/ < appendProps_.txt > appendProps.txt")
    shellExec(appbuildDir, "sed s/{#BuildDate}/" + buildDate[:10] + "/ < appendProps.txt > appendProps_.txt")
    shellExec(appbuildDir, "sed s/{#CommitHash}/" + commitHash + "/ < appendProps_.txt > appendProps.txt")
    logStep("Appending version properties to System/Rsrc/Strings.odc")
    runbbscript("appbuild/appendProps.txt")

def updateBbscript():
    if not args.test:
        logStep("Updating bbscript.exe")
        shellExec(bbDir, "mv bbscript.exe " + buildDir + "/")
    else:
        logStep("Removing bbscript.exe becaue this is a test build")
        shellExec(bbDir, "rm bbscript.exe ")

def buildSetupFile():
    logStep("Building " + outputNamePrefix + "-setup.exe file using InnoSetup")
    deleteBbFile("StdLog.txt");
    deleteBbFile("wine_out.txt");
    deleteBbFile("README.txt");
    shellExec(bbDir, "rm -R Cons Interp Script appbuild", False)
    shellExec(bbDir, iscc + " - < Win/Rsrc/BlackBox.iss" \
                  + '  "/dAppVersion=' + appVersion
                  + '" "/dAppVerName=' + appVerName
                  + '" "/dVersionInfoVersion=' + versionInfoVersion
                  + '"', False) # a meaningless error is displayed
    shellExec(bbDir, "mv Output/setup.exe " + outputPathPrefix + "-setup.exe")
    shellExec(bbDir, "rm -R Output")

def buildZipFile():
    deleteBbFile("LICENSE.txt")
    logStep("Zipping package to file " + outputNamePrefix + ".zip")
    shellExec(bbDir, "zip -r " + outputPathPrefix + ".zip *")

def updateCommitHash():
    if not args.test:
        logStep("Updating commit hash for branch '" + branch + "'")
        hashFile = open(hashFilePath(), "w")
        hashFile.write(commitHash)
        hashFile.close()

def incrementBuildNumber():
    if not args.test:
        logStep("Updating build number to " + str(buildNum + 1))
        numberFile.seek(0)
        numberFile.write(str(buildNum+1))
        numberFile.truncate()
        numberFile.close()

def cleanup():
    if not args.test:
        logStep("Cleaning up")
        shellExec(buildDir, "rm -R -f " + bbDir)

def renameLog():
    if not args.test:
        logStep("Renaming 'logFile.html' to '" + outputNamePrefix + "-buildlog.html'")
        global logFile
        logFile.close()
        logFile = None
        shellExec(unstableDir, "mv logFile.html " + outputPathPrefix + "-buildlog.html")

if args.test:
    unstableDir = buildDir + "/" + testName
    stableDir = unstableDir
    if (os.path.exists(bbDir)):
        shellExec(buildDir, "rm -R -f " + bbDir)
    if (os.path.exists(unstableDir)):
        shellExec(buildDir, "rm -R -f " + testName)
    shellExec(buildDir, "mkdir " + testName)
if os.path.exists(bbDir):  # previous build is still running or was terminated after an error
    logVerbose("no build because directory '" + bbDir + "' exists")
    sys.exit()
if repositoryLocked():
    logVerbose("no build because repository is locked; probably due to sync process")
    sys.exit()
if selectBranch() == None:
    logVerbose("no build because no new commit in any branch")
    sys.exit()

updateCommitHash() # if not args.test

# this file contains the build number to be used for this build; incremented after successfull build
numberFile = open(buildDir + "/" + "number", "r+")

buildNum = int(numberFile.readline().strip())
openLog()

log("<h2>Build " + str(buildNum) + " from '" + branch + "' at " + buildDate + "</h2>")
log("<h3>git commit hash: " + commitHash + "</h3>")

logStep("Cloning repository into temporary folder '" + bbName + "'")
shellExec(buildDir, "git clone " + localRepository + " " + bbDir)

if branch != "master":
    logStep("Checking out branch '" + branch + "'")
    shellExec(bbDir, "git checkout " + branch, False)

if not os.path.exists(appbuildDir + "/AppVersion.txt"):
    cleanup() # if not args.test
    logStep('No build because file "appbuild/AppVersion.txt" not in branch')
    sys.exit()

print "<br/>Build " + str(buildNum) + " from '" + branch + "' at " + buildDate + "<br/>" # goes to buildlog.html

appVersion = open(appbuildDir + "/AppVersion.txt", "r").readline().strip()
appVerName = getAppVerName(appVersion)
versionInfoVersion = getVersionInfoVersion(appVersion, buildNum)
finalRelease = isFinal(appVersion)
outputNamePrefix = "blackbox-" + appVersion + ("" if finalRelease else ("." + str(buildNum).zfill(3)))
outputDir = stableDir if finalRelease else unstableDir + "/" + branch
outputPathPrefix = outputDir + "/" + outputNamePrefix
if not os.path.exists(outputDir):
    shellExec(buildDir, "mkdir " + outputDir)

prepareCompileAndLink()
compileAndLink() #1
buildBbscript()
compileAndLink() #2
buildBbscript()
compileAndLink() #3
appendSystemProperties()
updateBbscript()
buildSetupFile()
buildZipFile()
# if not args.test
incrementBuildNumber()
cleanup()
renameLog()
