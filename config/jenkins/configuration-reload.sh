#!/usr/bin/env bash

set -e

JENKINS_HOME=<JENKINS_HOME>
# List of secrets created by Kubernetes
CONFIGSECRETS="passwords jenkinssp cloudconfig jenkinsconfig"

# Create test-infra repo if it does not exist
if [[ ! -d ${JENKINS_HOME}/test-infra ]]; then
    cd ${JENKINS_HOME}
    git clone \
        --depth 1 \
        --filter=blob:none \
        --no-checkout \
        https://github.com/cyandevs/test-infra
    cd ${JENKINS_HOME}/test-infra
    git checkout jenkins-test -- config/jenkins
    exit 0
fi

# Pull latest changes
cd ${JENKINS_HOME}/test-infra
git fetch

# Determine if changes occurred
LOCAL=$(git rev-parse master)
REMOTE=$(git rev-parse origin/master)
FILES=$(git diff --name-only ${LOCAL} ${REMOTE} -- config/jenkins/configuration | grep "yml")

if [[ ! -z ${FILES+x} ]]; then
    git pull
    if [[ -d ${JENKINS_HOME}/configuration_old ]]; then
        rm -rf ${JENKINS_HOME}/configuration_old
    fi
    mv ${JENKINS_HOME}/configuration ${JENKINS_HOME}/configuration_old
    cp --recursive config/jenkins/configuration ${JENKINS_HOME}/configuration

    # Apply secrets
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
    find ${JENKINS_HOME}/configuration/jobs -type f -name "*.yml" -exec sed -i "s/<JENKINS_REMOTE_TRIGGER_TOKEN>/${JENKINS_REMOTE_TRIGGER_TOKEN}/" {} +

    # Schedule rolling restart
    kubectl rollout restart deployment/jenkins-master
fi
