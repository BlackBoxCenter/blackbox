#!/usr/bin/python

# Automated build of the BlackBox Component Builder for Windows under Linux Debian 7.
# Looks at branches 'master' and 'development'.
#
# Ivan Denisov, Josef Templ
#
# Creates 3 artefacts:
# 1. a build log file named blackbox-<AppVersion>.<buildnr>-buildlog.html
# 2. a Windows installer file named blackbox-<AppVersion>.<buildnr>-setup.exe
# 3. a zipped package named blackbox-<AppVersion>-<buildnr>.zip
# In case of building a final release, buildnr is not included.
#
# By always rebuilding dev0.exe it avoids problems with changes in the symbol or object file formats
# and acts as a rigorous test for some parts of BlackBox, in particular for the compiler itself.
#
# A note on error handling:
# Stops building when a shell command writes to stderr, unless stopOnError is False.
# Stops building when there is a Python exception.
# Leaves temporary directory 'bb' in place in order to signal that the build has not been finished.
# If an error is encountered in the BlackBox compiler or linker, 'bb' will be removed and the
# branch's hash file will be updated but not the build number file.
# 
# TODO git checkout reports a message on stderr but it works, so it is ignored
# TODO detect errors in BlackBox compiler or linker
# TODO at least add a test for starting BlackBox using Xvfb

from subprocess import Popen, PIPE
import sys, datetime, fileinput, os.path

buildDate = datetime.datetime.now().isoformat()
buildDir = "/var/www/tribiq/makeapp"
bbName = "bb"
bbDir = buildDir + "/" + bbName
appbuildDir = bbDir + "/appbuild"
localRepository = "/var/www/git/blackbox.git" 
unstableDir = "/var/www/tribiq/unstable" 
stableDir = "/var/www/tribiq/stable"
wine = "/usr/local/bin/wine" 
iscc = "/usr/local/bin/iscc"
windres="/usr/bin/i586-mingw32msvc-windres"
branch = None
commitHash = None
logFile = None

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
    branch = "master"
    if needsRebuild():
        return branch
    branch = "development"
    if needsRebuild():
        return branch
    return None

def openLog():
    global logFile
    logFile = open(unstableDir + "/logFile.html", "w")
    
def log(text, startMarkup="", endMarkup=""):
    if text != "" and logFile != None:    
        for line in text.split("\n"):
            logFile.write(startMarkup + line + endMarkup + "<br/>\n")
        logFile.flush()

def logErr(text): # use color red
    log(text, '<font color="#FF0000">', '</font>')

def logStep(text): # use bold font
    log(text, '<b>', '</b>')

def shellExec(wd, cmd, stopOnError=True):
    log("shellExec: " + "cd " + wd + " && " + cmd)
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
        sys.exit()

def prepareCompileAndLink():
    logStep("Preparing BlackBox.rc")
    vrsn = versionInfoVersion.replace(".", ",")
    shellExec(bbDir + "/Win/Rsrc", "mv BlackBox.rc BlackBox.rc_template")
    shellExec(bbDir + "/Win/Rsrc", "sed s/{#VERSION}/" + vrsn + "/ < BlackBox.rc_template > BlackBox.rc")
    shellExec(bbDir + "/Win/Rsrc", "rm BlackBox.rc_template")
    logStep("Creating the BlackBox.res resource file")
    shellExec(bbDir + "/Win/Rsrc", windres + " -i BlackBox.rc -o BlackBox.res")
    logStep("Preparing dev0.exe")
    shellExec(buildDir, "cp dev0.exe " + bbDir + "/")

def errorInBlackBox():
    return False  #TODO

def buildDev0():
    logStep("Building command line compiler dev0.exe")
    shellExec(bbDir, wine + " dev0.exe < appbuild/newdev0.txt 2>&1")
    shellExec(bbDir, "mv newdev0.exe dev0.exe && chmod a+x dev0.exe")
    shellExec(bbDir, "rm -R Code Sym */*/*.osf */*/*.ocf BlackBox.exe")

def compileAndLink():
    logStep("Setting system properties in build.txt")
    shellExec(appbuildDir, "sed s/{#AppVersion}/" + appVersion + "/ < build.txt > build_.txt")
    shellExec(appbuildDir, "sed s/{#BuildNum}/" + str(buildNum) + "/ < build_.txt > build.txt")
    shellExec(appbuildDir, "sed s/{#BuildDate}/" + buildDate[:10] + "/ < build.txt > build_.txt")
    shellExec(appbuildDir, "sed s/{#CommitHash}/" + commitHash + "/ < build_.txt > build.txt")
    logStep("Compiling and linking BlackBox")
    shellExec(bbDir, wine + " dev0.exe < appbuild/build.txt 2>&1")
    if errorInBlackBox():
        updateCommitHash()
        cleanup()
        logErr("build terminated due to BlackBox compile/link error") 
        sys.exit()
    logStep("Moving Code and Sym to System") 
    shellExec(bbDir, "mv Code System/ && mv Sym System/")

def buildSetupFile():
    logStep("Building " + outputNamePrefix + "-setup.exe file")
    shellExec(bbDir, "cp Win/Rsrc/BlackBox.iss appbuild/")
    shellExec(appbuildDir, iscc + " - < ./BlackBox.iss" \
                  + '  "/dAppVersion=' + appVersion
                  + '" "/dAppVerName=' + appVerName
                  + '" "/dVersionInfoVersion=' + versionInfoVersion
                  + '"', False)
    shellExec(appbuildDir + "/Output", "mv setup.exe " + outputPathPrefix + "-setup.exe")

def updateDev0():
    # if setup file creation was successfull, we know that the new dev0.exe works well
    logStep("Updating dev0.exe")
    shellExec(bbDir, "mv dev0.exe " + buildDir + "/")

def buildZipFile():
    logStep("Removing auxiliary files and directories") 
    shellExec(bbDir, "rm -R *.txt appbuild Cons Interp Script")
    logStep("Zipping package to file " + outputNamePrefix + ".zip") 
    shellExec(bbDir, "zip -r " + outputPathPrefix + ".zip *")

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

def updateCommitHash():
    logStep("Updating commit hash for branch '" + branch + "'") 
    hashFile = open(hashFilePath(), "w")
    hashFile.write(commitHash)
    hashFile.close()

def incrementBuildNumber():
    logStep("Updating build number to " + str(buildNum + 1)) 
    numberFile.seek(0)
    numberFile.write(str(buildNum+1))
    numberFile.truncate()
    numberFile.close()

def cleanup():
    logStep("Cleaning up") 
    shellExec(buildDir, "rm " + bbName + " -R")

def closeLog():
    logStep("Renaming 'logFile.html' to '" + outputNamePrefix + "-buildlog.html'")
    global logFile
    logFile.close()
    logFile = None
    shellExec(unstableDir, "mv logFile.html " + outputPathPrefix + "-buildlog.html")

if os.path.exists(bbDir):  # previous build is still running or was terminated after an error
    sys.exit()
if repositoryLocked():
    sys.exit()
if selectBranch() == None:
    sys.exit()

# this file contains the build number to be used for this build; incremented after successfull build
numberFile = open(buildDir + "/" + "number", "r+")

buildNum = int(numberFile.readline().strip())
openLog()

print "<br/>Build " + str(buildNum) + " from '" + branch + "' at " + buildDate + "<br/>"
log("<h2>Build " + str(buildNum) + " from '" + branch + "' at " + buildDate + "</h2>")
log("git commit hash is: " + commitHash)

logStep("Cloning repository into temporary folder '" + bbName + "'") 
shellExec(buildDir, "git clone " + localRepository + " " + bbName)

logStep("Checking out branch '" + branch + "' into temporary folder '" + bbName + "'") 
shellExec(bbDir, "git checkout " + branch, False)

appVersion = open(appbuildDir + "/AppVersion.txt", "r").readline().strip()
appVerName = getAppVerName(appVersion)
versionInfoVersion = getVersionInfoVersion(appVersion, buildNum)
finalRelease = isFinal(appVersion)
outputNamePrefix = "blackbox-" + appVersion + ("" if finalRelease else ("." + str(buildNum).zfill(3)))
outputDir = stableDir if finalRelease else unstableDir
outputPathPrefix = outputDir + "/" + outputNamePrefix

prepareCompileAndLink()
compileAndLink() #1
buildDev0()
compileAndLink() #2
buildDev0()
compileAndLink() #3
buildSetupFile()
updateDev0()
buildZipFile()
updateCommitHash()
incrementBuildNumber()
cleanup()
closeLog()
