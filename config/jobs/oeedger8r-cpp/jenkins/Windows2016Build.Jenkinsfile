// Pull Request Information
OE_PULL_NUMBER=env.OE_PULL_NUMBER?env.OE_PULL_NUMBER:"master"

// OS Version Configuration
WINDOWS_VERSION=env.WINDOWS_VERSION?env.WINDOWS_VERSION:"2016"

// Some Defaults
DOCKER_TAG=env.DOCKER_TAG?env.DOCKER_TAG:"latest"
COMPILER=env.COMPILER?env.COMPILER:"clang-7"
String[] BUILD_TYPES=['Debug', 'RelWithDebInfo', 'Release']

// Shared library config, check out common.groovy!
SHARED_LIBRARY="/config/jobs/oeedger8r-cpp/jenkins/common.groovy"

pipeline {
    options {
        timeout(time: 60, unit: 'MINUTES') 
    }
    agent { label "SGXFLC-Windows-${WINDOWS_VERSION}-Docker" }

    stages {
        stage('Build'){
            steps{
                script{
                    for(BUILD_TYPE in BUILD_TYPES){
                        stage("Windows ${WINDOWS_VERSION} Build - ${BUILD_TYPE}"){
                            script {
                                cleanWs()
                                checkout scm
                                def runner = load pwd() + "${SHARED_LIBRARY}"
                                runner.cleanup()
                                try{
                                    runner.checkout("${OE_PULL_NUMBER}")
                                    runner.cmakeBuildoeedger8r("${BUILD_TYPE}","${COMPILER}")
                                } catch (Exception e) {
                                    // Do something with the exception 
                                    error "Program failed, please read logs..."
                                } finally {
                                    runner.cleanup()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
