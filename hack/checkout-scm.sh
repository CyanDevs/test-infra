set -e

git clone --recursive https://github.com/${REPO_OWNER}/${REPO_NAME}.git && cd ${REPO_NAME} && git checkout ${PULL_PULL_SHA}
