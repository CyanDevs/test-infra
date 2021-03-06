#!/usr/bin/env bash

set -e
set +x

JENKINS_HOME=<JENKINS_HOME>
BRANCH="master"

clone_configs () {
    git clone \
        --depth 2 \
        --filter=blob:none \
        --no-checkout \
        --single-branch \
        --branch ${BRANCH} \
        https://github.com/openenclave/test-infra \
        ${JENKINS_HOME}/test-infra
    git -C ${JENKINS_HOME}/test-infra/ checkout ${BRANCH} -- config/jenkins
}

apply_secrets () {

    # Backup configuration to configuration_old directory
    if [[ -d ${JENKINS_HOME}/configuration_old ]]; then
        rm -rf ${JENKINS_HOME}/configuration_old
    fi
    if [[ -d ${JENKINS_HOME}/configuration ]]; then
        mv ${JENKINS_HOME}/configuration ${JENKINS_HOME}/configuration_old
    fi

    # Copy over new configuration to Jenkins
    cp --recursive ${JENKINS_HOME}/test-infra/config/jenkins/configuration ${JENKINS_HOME}/configuration

    # Overwrite variables with secrets
    sed -i "s/<JENKINSADMIN_EMAIL>/${JENKINSADMIN_EMAIL}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s@<AZURE_KEYVAULT_URL>@${AZURE_KEYVAULT_URL}@" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<DNS_LABAEL>/${DNS_LABEL}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<AZURE_LOCATION>/${AZURE_LOCATION}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<AZURE_VM_RESOURCE_GROUP>/${AZURE_VM_RESOURCE_GROUP}/" ${JENKINS_HOME}/configuration/clouds.yml
    sed -i "s/<AZURE_VM_LOCATION>/${AZURE_VM_LOCATION}/" ${JENKINS_HOME}/configuration/clouds.yml
    sed -i "s/<AZURE_VM_GALLERY_NAME>/${AZURE_VM_GALLERY_NAME}/" ${JENKINS_HOME}/configuration/clouds.yml
    sed -i "s/<AZURE_VM_GALLERY_RESOURCE_GROUP>/${AZURE_VM_GALLERY_RESOURCE_GROUP}/" ${JENKINS_HOME}/configuration/clouds.yml
    sed -i "s/<AZURE_VM_GALLERY_SUBSCRIPTION_ID>/${AZURE_VM_GALLERY_SUBSCRIPTION_ID}/" ${JENKINS_HOME}/configuration/clouds.yml
    sed -i "s/<JENKINSADMIN_PASSWORD>/${JENKINSADMIN_PASSWORD}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<OEADMIN_PASSWORD>/${OEADMIN_PASSWORD}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<AZURE_SP_CLIENT_ID>/${AZURE_SERVICE_PRINCIPAL_CLIENT_ID}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<AZURE_SP_SUBSCRIPTION_ID>/${AZURE_SERVICE_PRINCIPAL_SUBSCRIPTION_ID}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<AZURE_SP_TENANT_ID>/${AZURE_SERVICE_PRINCIPAL_TENANT_ID}/" ${JENKINS_HOME}/configuration/jenkins.yml
    sed -i "s/<AZURE_SP_SECRET>/${AZURE_SERVICE_PRINCIPAL_SECRET}/" ${JENKINS_HOME}/configuration/jenkins.yml

    # Change remote trigger token on every job
    find ${JENKINS_HOME}/configuration/jobs -type f -name "*.yml" -exec sed -i "s/<JENKINS_REMOTE_TRIGGER_TOKEN>/${JENKINS_REMOTE_TRIGGER_TOKEN}/" {} +

    # Add latest commit to welcome message
    COMMIT=$(git -C ${JENKINS_HOME}/test-infra rev-parse ${BRANCH})
    sed -i "s/<GIT_COMMIT>/${COMMIT}/" ${JENKINS_HOME}/configuration/jenkins.yml

    # Schedule rolling restart
    kubectl rollout restart deployment/jenkins-master

}

remove_locks () {

    # Remove git locks if exists
    # this occurs due to git operations that are unusually slow in previous runs that were killed by the job timeout
    LOCK_FILES=(
        .git/index.lock
        .git/shallow.lock
        .git/logs/HEAD.lock
        .git/HEAD.lock
    )
    for LOCK_FILE in "${LOCK_FILES[@]}"; do
        if [[ -f ${JENKINS_HOME}/test-infra/${LOCK_FILE} ]]; then
            rm ${JENKINS_HOME}/test-infra/${LOCK_FILE}
        fi
    done

}

# Create test-infra repo if it does not exist
if [[ ! -d ${JENKINS_HOME}/test-infra ]]; then
    echo "No git repository detected. Cloning new and applying configurations..."
    clone_configs
    apply_secrets
    exit 0
fi

# Determine current commit
if [[ -f ${JENKINS_HOME}/configuration/jenkins.yml ]]; then
    LOCAL=$(grep "Jenkins Master is currently on commit:" /var/jenkins_home/configuration/jenkins.yml | cut -d ':' -f 2 | sed 's/ //g')
    # Catch edge case where if commit is somehow unset, make sure all variables and secrets are applied
    if [[ ${LOCAL} == "<GIT_COMMIT>" ]]; then
        apply_secrets
        exit 0
    fi
fi

# Determine if there are new commits on master
remove_locks
git -C ${JENKINS_HOME}/test-infra/ fetch --depth=1
REMOTE=$(git -C ${JENKINS_HOME}/test-infra rev-parse origin/${BRANCH})

# If a new commit is available and whether changes are made to configuration files
if [[ "${LOCAL}" != "${REMOTE}" ]]; then
    echo "Local:  ${LOCAL}"
    echo "Remote: ${REMOTE}"
    if git -C ${JENKINS_HOME}/test-infra/ diff --name-only ${LOCAL} ${REMOTE} -- config/jenkins/configuration | grep "yml"; then
        echo "Updating configurations from commit ${LOCAL} to ${REMOTE}"
        # Pull in new commits
        git -C ${JENKINS_HOME}/test-infra/ clean -dfx
        git -C ${JENKINS_HOME}/test-infra/ checkout -- config/jenkins
        git -C ${JENKINS_HOME}/test-infra/ reset --hard origin/${BRANCH}
        apply_secrets
    else
        echo "No configuration files (.yml) were updated between the two commits"
    fi
else
    echo "Already at latest commit ${LOCAL}. No update needed"
fi
