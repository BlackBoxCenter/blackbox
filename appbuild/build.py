#!/usr/bin/python
#
# Python 2.7 script for building the BlackBox Component Builder for Windows under Linux Debian 7.
# Looks at all branches and puts the output into the branch's output folder 'unstable/<branch>'
# unless building a stable (final) release, which is always put into folder 'stable'.
# A stable release is one that does not have a development phase in appVersion and that is built for branch 'master'.
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
# For downloadable zip and exe files, additional files with file name appendix "_sha256.txt" are created.
# They contain the SHA-256 key for the respective file, which allows for manually checking the file's integrity.
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
import sys, datetime, fileinput, os.path, argparse, urllib2, time
import xml.etree.ElementTree as ET

buildDate = datetime.datetime.now().isoformat()[:19]
buildDir = "/var/www/zenario/makeapp"
bbName = "bb"
bbDir = buildDir + "/" + bbName
appbuildDir = bbDir + "/appbuild"
localRepository = "/var/www/git/blackbox.git"
unstableDir = "/var/www/zenario/unstable"
stableDir = "/var/www/zenario/stable"
wine = "/usr/local/bin/wine"
xvfb = "xvfb-run --server-args='-screen 1, 1024x768x24' "
bbscript = xvfb + wine + " bbscript.exe"
bbchanges = xvfb + wine + " " + buildDir + "/bbchanges.exe /USE " + bbDir + " /LOAD ScriptChanges"
iscc = "/usr/local/bin/iscc"
windres="/usr/bin/i586-mingw32msvc-windres"
testName = "testbuild"
branch = None
commitHash = None
logFile = None
outputNamePrefix = None # until appVersion and build number are known
buildNumberIncremented = False

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
    cmd = "cd " + wd + " && " + cmd
    logShell(cmd)
    (stdout, stderr) = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True).communicate()
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
        print "--- build aborted ---\n"
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

def isStable(appVersion):
    return appVersion.find("-") < 0 and branch == "master"

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
    shellExec(bbDir, "sha256sum BlackBox.exe > BlackBox.exe_sha256.txt")

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
    shellExec(appbuildDir, 'sed s/{#BuildBranch}/"' + branch + '"/ < appendProps_.txt > appendProps.txt')
    shellExec(appbuildDir, "sed s/{#CommitHash}/" + commitHash + "/ < appendProps.txt > appendProps_.txt")
    logStep("Appending version properties to System/Rsrc/Strings.odc")
    runbbscript("appbuild/appendProps_.txt")

def updateBbscript():
    if not args.test and branch == "master":
        logStep("Updating bbscript.exe")
        shellExec(bbDir, "mv bbscript.exe " + buildDir + "/")
    else:
        logStep("Removing bbscript.exe")
        shellExec(bbDir, "rm bbscript.exe ")

def get_fixed_version_id(versions_file, target):
    tree = ET.parse(versions_file)
    root = tree.getroot()
    for version in root.findall('version'):
        if version.findtext('name') == target:
            return version.findtext('id')
    return "-1" # unknown

def addChanges():
    if branch == "master" or args.test:
        logStep("downloading xml files from Redmine")
        versions_file = bbDir + "/blackbox_versions.xml"
        url = "http://redmine.blackboxframework.org/projects/blackbox/versions.xml"
        with open(versions_file, 'wb') as out_file:
            out_file.write(urllib2.urlopen(url).read())
        minusPos = appVersion.find("-")
        target = appVersion if minusPos < 0 else appVersion[0:minusPos]
        fixed_version_id = get_fixed_version_id(versions_file, target)
        # status_id=5 means 'Closed', limit above 100 is not supported by Redmine
        url = "http://redmine.blackboxframework.org/projects/blackbox/issues.xml?status_id=5&fixed_version_id=" + fixed_version_id + "&offset=0&limit=100"
        issues_file1 = bbDir + "/blackbox_issues100.xml"
        with open(issues_file1, 'wb') as out_file:
            out_file.write(urllib2.urlopen(url).read())
        url = "http://redmine.blackboxframework.org/projects/blackbox/issues.xml?status_id=5&fixed_version_id=" + fixed_version_id + "&offset=100&limit=100"
        issues_file2 = bbDir + "/blackbox_issues200.xml"
        with open(issues_file2, 'wb') as out_file:
            out_file.write(urllib2.urlopen(url).read())
        logStep("converting to BlackBox_" + appVersion + "_Changes.odc/.html")
        bbres = call(bbchanges + " >" + bbDir + "/wine_out.txt 2>&1", shell=True)
        logStep("removing xml files")
        shellExec(".", "rm " + versions_file + " " + issues_file1 + " " + issues_file2)
        logStep("moving file BlackBox_" + appVersion + "_Changes.html to outputDir")
        shellExec(".", "mv " + bbDir + "/BlackBox_" + appVersion + "_Changes.html " + outputPathPrefix + "-changes.html")

def buildSetupFile():
    logStep("Building " + outputNamePrefix + "-setup.exe file using InnoSetup")
    deleteBbFile("StdLog.txt");
    deleteBbFile("wine_out.txt");
    deleteBbFile("README.txt");
    shellExec(bbDir, "rm -R Script appbuild")
    shellExec(bbDir, iscc + " - < Win/Rsrc/BlackBox.iss" \
                  + '  "/dAppVersion=' + appVersion
                  + '" "/dAppVerName=' + appVerName
                  + '" "/dVersionInfoVersion=' + versionInfoVersion
                  + '"', False) # a meaningless error is displayed
    shellExec(bbDir, "mv Output/setup.exe " + outputPathPrefix + "-setup.exe", not args.test)
    shellExec(outputDir, "sha256sum " + outputNamePrefix + "-setup.exe > " + outputNamePrefix + "-setup.exe_sha256.txt", not args.test)
    shellExec(bbDir, "rm -R Output", not args.test)

def buildZipFile():
    deleteBbFile("LICENSE.txt")
    logStep("Zipping package to file " + outputNamePrefix + ".zip")
    shellExec(bbDir, "zip -r " + outputPathPrefix + ".zip *")
    shellExec(outputDir, "sha256sum " + outputNamePrefix + ".zip > " + outputNamePrefix + ".zip_sha256.txt")

def updateCommitHash():
    if not args.test:
        logStep("Updating commit hash for branch '" + branch + "'")
        hashFile = open(hashFilePath(), "w")
        hashFile.write(commitHash)
        hashFile.close()

def incrementBuildNumber():
    global buildNumberIncremented
    if not buildNumberIncremented:
        logStep("Updating build number to " + str(buildNum + 1))
        numberFile.seek(0)
        numberFile.write(str(buildNum+1))
        numberFile.truncate()
        numberFile.close()
        buildNumberIncremented = True

def cleanup():
    if not args.test:
        logStep("Cleaning up")
        shellExec(buildDir, "rm -R -f " + bbDir)

def renameLog():
    global logFile
    logFile.close()
    logFile = None
    if not args.test and outputNamePrefix != None:
        logStep("Renaming 'logFile.html' to '" + outputNamePrefix + "-buildlog.html'")
        shellExec(unstableDir, "mv logFile.html " + outputPathPrefix + "-buildlog.html")

if args.test:
    buildNumberIncremented = True # avoid side effect when testing
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
# option -q suppresses the progress reporting on stderr
shellExec(buildDir, "git clone -q --branch " + branch + " " + localRepository + " " + bbDir)

if not os.path.exists(appbuildDir + "/AppVersion.txt"):
    cleanup() # if not args.test
    logStep('No build because file "appbuild/AppVersion.txt" not in branch')
    sys.exit()

print "<br/>Build " + str(buildNum) + " from '" + branch + "' at " + buildDate + "<br/>" # goes to buildlog.html

appVersion = open(appbuildDir + "/AppVersion.txt", "r").readline().strip()
appVerName = getAppVerName(appVersion)
versionInfoVersion = getVersionInfoVersion(appVersion, buildNum)
stableRelease = isStable(appVersion)
outputNamePrefix = "blackbox-" + appVersion + ("" if stableRelease else ("." + str(buildNum).zfill(3)))
outputDir = stableDir if stableRelease else unstableDir + "/" + branch
outputPathPrefix = outputDir + "/" + outputNamePrefix
if stableRelease and os.path.exists(outputPathPrefix + ".zip"):
    #for rebuilding a stable release remove the output files manually from the stable dir
    cleanup() # if not args.test
    logStep('Cannot rebuild stable release ' + appVersion + '.')
    print "Cannot rebuild stable release " + appVersion + ".<br/>" # goes to buildlog.html
    sys.exit()
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
addChanges()
buildSetupFile()
buildZipFile()
# if not args.test
incrementBuildNumber()
cleanup()
renameLog()
