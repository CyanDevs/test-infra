// Pull Request Information
OE_PULL_NUMBER=env.OE_PULL_NUMBER?env.OE_PULL_NUMBER:"master"

// Repo hardcoded
REPO="oeedger8r-cpp"

// Shared library config, check out common.groovy!
SHARED_LIBRARY="/config/jobs/"+"${REPO}"+"/jenkins/common.groovy"

pipeline {
    options {
        timeout(time: 30, unit: 'MINUTES') 
    }
    agent { label 'ACC-RHEL-8' }
    stages {
        stage('RHEL 8 Build - Debug') {
            steps {
                script {
                    cleanWs()
                    checkout scm
                    def runner = load pwd() + "${SHARED_LIBRARY}"
                    runner.cleanup("${REPO}")
                    try {
                        runner.checkout("${REPO}", "${OE_PULL_NUMBER}")
                        runner.cmakeBuild("${REPO}","Debug")
                    } catch (Exception e) {
                        // Do something with the exception 
                        error "Program failed, please read logs..."
                    } finally {
                        runner.cleanup("${REPO}")
                    }
                }
            }
        }
        stage('RHEL 8 Build - Release') {
            steps {
                script {
                    cleanWs()
                    checkout scm
                    def runner = load pwd() + "${SHARED_LIBRARY}"
                    runner.cleanup("${REPO}")
                    try {
                        runner.checkout("${REPO}", "${OE_PULL_NUMBER}")
                        runner.cmakeBuild("${REPO}","Release")
                    } catch (Exception e) {
                        // Do something with the exception 
                        error "Program failed, please read logs..."
                    } finally {
                        runner.cleanup("${REPO}")
                    }
                }
            }
        }
        stage('RHEL 8 Build - RelWithDebInfo') {
            steps {
                script {
                    cleanWs()
                    checkout scm
                    def runner = load pwd() + "${SHARED_LIBRARY}"
                    runner.cleanup("${REPO}")
                    try {
                        runner.checkout("${REPO}", "${OE_PULL_NUMBER}")
                        runner.cmakeBuild("${REPO}","RelWithDebInfo")
                    } catch (Exception e) {
                        // Do something with the exception 
                        error "Program failed, please read logs..."
                    } finally {
                        runner.cleanup("${REPO}")
                    }
                }
            }
        }
    }
}
