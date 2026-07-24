#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Gradle Wrapper for Android project.

Downloads the official gradle-wrapper.jar and creates the complete
wrapper setup (gradlew, gradlew.bat, gradle-wrapper.properties).

This ensures the project can be built on any machine without
requiring a pre-installed Gradle distribution.
"""

import os
import sys
import urllib.request
import zipfile
import shutil
import stat

GRADLE_VERSION = "8.5"
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ANDROID_DIR = PROJECT_ROOT

def setup_gradle_wrapper():
    """Create complete Gradle wrapper with official jar"""
    
    wrapper_dir = os.path.join(ANDROID_DIR, "gradle", "wrapper")
    os.makedirs(wrapper_dir, exist_ok=True)
    
    jar_path = os.path.join(wrapper_dir, "gradle-wrapper.jar")
    props_path = os.path.join(wrapper_dir, "gradle-wrapper.properties")
    gradlew_path = os.path.join(ANDROID_DIR, "gradlew")
    gradlew_bat_path = os.path.join(ANDROID_DIR, "gradlew.bat")
    
    # Download gradle-wrapper.jar
    jar_url = f"https://raw.githubusercontent.com/gradle/gradle/v{GRADLE_VERSION}.0/gradle/wrapper/gradle-wrapper.jar"
    
    print(f"[1/4] Downloading gradle-wrapper.jar (Gradle {GRADLE_VERSION})...")
    print(f"  URL: {jar_url}")
    
    try:
        req = urllib.request.Request(jar_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            jar_data = response.read()
        
        with open(jar_path, 'wb') as f:
            f.write(jar_data)
        
        print(f"  [OK] Downloaded {len(jar_data)} bytes -> {jar_path}")
        
        # Verify it's a valid jar
        try:
            with zipfile.ZipFile(jar_path, 'r') as zf:
                names = zf.namelist()
                if "org/gradle/wrapper/GradleWrapperMain.class" in names:
                    print(f"  [OK] Verified: Contains GradleWrapperMain class")
                else:
                    print(f"  [WARN] Jar doesn't contain GradleWrapperMain - may not work")
                    print(f"         Contents: {', '.join(names[:10])}...")
        except zipfile.BadZipFile:
            print(f"  [WARN] Downloaded file is not a valid ZIP/jar")
            # The raw.githubusercontent might serve a redirect differently
            # Try alternative URL
            alt_url = f"https://github.com/gradle/gradle/raw/v{GRADLE_VERSION}.0/gradle/wrapper/gradle-wrapper.jar"
            print(f"  Trying alternative URL: {alt_url}")
            req2 = urllib.request.Request(alt_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=30) as response2:
                jar_data2 = response2.read()
            with open(jar_path, 'wb') as f:
                f.write(jar_data2)
            try:
                with zipfile.ZipFile(jar_path, 'r') as zf2:
                    names2 = zf2.namelist()
                    if "org/gradle/wrapper/GradleWrapperMain.class" in names2:
                        print(f"  [OK] Verified with alternative URL")
            except zipfile.BadZipFile:
                print(f"  [ERROR] Both download attempts failed. Please download manually:")
                print(f"    wget {jar_url} -O gradle/wrapper/gradle-wrapper.jar")
                return False
                
    except urllib.error.URLError as e:
        print(f"  [WARN] Download failed: {e}")
        print(f"  Trying alternative approach...")
        
        # Alternative: download the full gradle distribution and extract wrapper
        dist_url = f"https://services.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip"
        print(f"  Downloading Gradle distribution: {dist_url}")
        
        try:
            dist_path = os.path.join(ANDROID_DIR, f"gradle-{GRADLE_VERSION}-bin.zip")
            req3 = urllib.request.Request(dist_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req3, timeout=120) as response3:
                with open(dist_path, 'wb') as f:
                    shutil.copyfileobj(response3, f)
            
            # Extract wrapper jar from distribution
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(dist_path, 'r') as zf:
                    # Find the wrapper jar
                    wrapper_entries = [n for n in zf.namelist() if 'gradle-wrapper.jar' in n]
                    if wrapper_entries:
                        zf.extract(wrapper_entries[0], tmpdir)
                        extracted = os.path.join(tmpdir, wrapper_entries[0])
                        shutil.copy2(extracted, jar_path)
                        print(f"  [OK] Extracted gradle-wrapper.jar from distribution")
                    else:
                        print(f"  [ERROR] gradle-wrapper.jar not found in distribution")
                        return False
            
            # Clean up distribution
            os.remove(dist_path)
            
        except Exception as e2:
            print(f"  [ERROR] Alternative approach also failed: {e2}")
            return False
    
    # Create gradle-wrapper.properties
    print(f"\n[2/4] Creating gradle-wrapper.properties...")
    props_content = f"""#Project-wide Gradle settings.
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.nonTransitiveRClass=true
# Gradle wrapper
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""
    with open(props_path, 'w', encoding='utf-8') as f:
        f.write(props_content)
    print(f"  [OK] Created {props_path}")
    
    # Create gradlew (Unix)
    print(f"\n[3/4] Creating gradlew (Unix) and gradlew.bat (Windows)...")
    
    gradlew_content = r'''#!/bin/sh

#
# Copyright © 2015-2021 the original authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

##############################################################################
#
#   Gradle start up script for POSIX generated by Gradle.
#
##############################################################################

# Attempt to set APP_HOME
# Resolve links: $0 may be a link
app_path=$0
while
    APP_HOME=${app_path%"${app_path##*/}"}  # leaves a trailing /; empty if no leading path
    [ -h "$app_path" ]
do
    ls=$( ls -ld -- "$app_path" )
    link=${ls#*' -> '}
    case $link in
      /*)   app_path=$link ;;
      *)    app_path=$APP_HOME$link ;;
    esac
done

APP_HOME=$( cd "${APP_HOME:-./}" > /dev/null && pwd -P ) || exit

# Use the maximum available, or set MAX_FD != -1 to use that value.
MAX_FD=maximum

warn () {
    echo "$*"
} >&2

die () {
    echo
    echo "$*"
    echo
    exit 1
} >&2

# OS specific support (must be 'true' or 'false').
cygwin=false
msys=false
darwin=false
nonstop=false
case "$( uname )" in
  CYGWIN* )         cygwin=true  ;;
  Darwin* )         darwin=true  ;;
  MSYS* | MINGW* )  msys=true    ;;
  NonStop* )         nonstop=true ;;
esac

CLASSPATH=$APP_HOME/gradle/wrapper/gradle-wrapper.jar

# Determine the Java command to use to start the JVM.
if [ -n "$JAVA_HOME" ] ; then
    if [ -x "$JAVA_HOME/jre/sh/java" ] ; then
        JAVACMD=$JAVA_HOME/jre/sh/java
    else
        JAVACMD=$JAVA_HOME/bin/java
    fi
    if [ ! -x "$JAVACMD" ] ; then
        die "ERROR: JAVA_HOME is set to an invalid directory: $JAVA_HOME

Please set the JAVA_HOME variable in your environment to match the
location of your Java installation."
    fi
else
    JAVACMD=java
    if ! command -v java >/dev/null 2>&1 ; then
        die "ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.

Please set the JAVA_HOME variable in your environment to match the
location of your Java installation."
    fi
fi

# Increase the maximum file descriptors if we can.
if ! "$cygwin" && ! "$darwin" && ! "$nonstop" ; then
    case $MAX_FD in
      max*)
        MAX_FD=$( ulimit -H -n ) ||
            warn "Could not query maximum file descriptor limit"
      ;;
    esac
    case $MAX_FD in
      '' | soft) :;;
      *)
        ulimit -n "$MAX_FD" ||
            warn "Could not set maximum file descriptor limit to $MAX_FD"
      ;;
    esac
fi

# Collect all arguments for the java command, stracks://gradle.org/releases/gradle.
# temporary file for arguments
if "$cygwin" || "$msys" ; then
    GRADLE_OPTS="$GRADLE_OPTS \"-Dfile.encoding=UTF-8\""
fi

# Collect all arguments for the java command;
#   * $DEFAULT_JVM_OPTS, $JAVA_OPTS, and $GRADLE_OPTS can contain fragments of
#     shell script including quotes and backslashes, so put them in temporary
#     variables and use eval to get array handling
set -- \
        "-Dorg.gradle.appname=$APP_BASE_NAME" \
        -classpath "$CLASSPATH" \
        org.gradle.wrapper.GradleWrapperMain \
        "$@"

# Stop when "xeli" is not available.
if ! "$cygwin" && ! "$msys" ; then
    exec "$JAVACMD" "$@"
fi

# For Cygwin or MSYS, convert paths to Windows format before running java
if "$cygwin" ; then
    # For Cygwin, switch paths to Windows format before running java
    CLASSPATH=$( cygpath --path --mixed "$CLASSPATH" )

    JAVACMD=$( cygpath --unix "$JAVACMD" )

fi

# Now convert the arguments - kludge for isssues with some programs on MSYS
if "$msys" ; then
    # For MSYS, convert paths to Windows format before running java
    CLASSPATH=$( cygpath --path --mixed "$CLASSPATH" )

    # We build the pattern for arguments to be converted via cygpath
    ROOTDIRSRAW=$( find -L / -maxdepth 1 -mindepth 1 -type d 2>/dev/null )
    SEP=""
    for dir in $ROOTDIRSRAW ; do
        ROOTDIRS="$ROOTDIRS$SEP$dir"
        SEP="|"
    done
    OURCYGPATTERN="(^($ROOTDIRS))"
    # Add a user-defined pattern to the cygpath arguments
    if [ "$GRADLE_CYGPATTERN" != "" ] ; then
        OURCYGPATTERN="$OURCYGPATTERN|($GRADLE_CYGPATTERN)"
    fi
    # Now convert the arguments - kludge for issues with mingw
    if [ $# -gt 0 ] ; then
        CMD=""
        while [ $# -gt 0 ] ; do
            arg="$1"
            if (( echo "$arg" | grep -q "$OURCYGPATTERN" ) && ( echo "$arg" | grep -qv "^--" )) ; then
                arg=$( cygpath --path --ignore --mixed "$arg" )
            fi
            CMD="$CMD $arg"
            shift
        done
        # Have to use eval because we need to use the shell to expand args
        eval "set -- $CMD"
    fi
fi

exec "$JAVACMD" "$@"
'''
    
    with open(gradlew_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(gradlew_content)
    
    # Make gradlew executable on Unix
    try:
        st = os.stat(gradlew_path)
        os.chmod(gradlew_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass
    
    # Create gradlew.bat (Windows)
    gradlew_bat_content = r'''@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem

@if "%DEBUG%"=="" @echo off
@rem ##########################################################################
@rem
@rem  Gradle startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
@rem This is normally unused
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%

@rem Resolve any "." and ".." in APP_HOME to make it shorter.
for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi

@rem Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS="-Xmx64m" "-Xms64m"

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if %ERRORLEVEL% equ 0 goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo the location of your Java installation. 1>&2

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME% 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo the location of your Java installation. 1>&2

goto fail

:execute
@rem Setup the command line

set CLASSPATH=%APP_HOME%\gradle\wrapper\gradle-wrapper.jar


@rem Execute Gradle
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% "-Dorg.gradle.appname=%APP_BASE_NAME%" -classpath "%CLASSPATH" org.gradle.wrapper.GradleWrapperMain %*

:end
@rem End local scope for the variables with windows NT shell
if %OS%==Windows_NT endlocal

:omega
exit /b %ERRORLEVEL%

:fail
exit /b 1
'''
    
    with open(gradlew_bat_path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(gradlew_bat_content)
    
    print(f"  [OK] Created {gradlew_path}")
    print(f"  [OK] Created {gradlew_bat_path}")
    
    # Verify
    print(f"\n[4/4] Verifying...")
    for path, desc in [
        (jar_path, "gradle-wrapper.jar"),
        (props_path, "gradle-wrapper.properties"),
        (gradlew_path, "gradlew"),
        (gradlew_bat_path, "gradlew.bat"),
    ]:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  [OK] {desc}: {size:,} bytes")
        else:
            print(f"  [FAIL] {desc}: not found")
            return False
    
    print(f"\n{'='*50}")
    print(f"  Gradle Wrapper Setup Complete!")
    print(f"{'='*50}")
    print(f"\n  Now you can build the Android app:")
    print(f"    Windows: gradlew.bat assembleDebug")
    print(f"    Unix:    ./gradlew assembleDebug")
    print(f"\n  For release:")
    print(f"    Windows: gradlew.bat assembleRelease")
    print(f"    Unix:    ./gradlew assembleRelease")
    
    return True

if __name__ == "__main__":
    success = setup_gradle_wrapper()
    sys.exit(0 if success else 1)
