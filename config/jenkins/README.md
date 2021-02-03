# Introduction 
This is used to setup and manage a scaling Jenkins service using the Azure Kubernetes Service.

Below are the notable service providers and last known working version.

| Service                  | Provider                              | Versions       |
| ------------------------ | ------------------------------------- | -------------- |
| Jenkins                  | Jenkins CI                            | 2.263.3        |
| Infrastructure           | Kubernetes & Azure Kubernetes Service | 1.19.3         |
| Storage                  | Azure Persistent File Shares          | N/A            |
| Ingress                  | F5 Nginx Ingress Controller           | v0.41.2        |
| SSL Certificate Manager  | Jetstack Cert Manager                 | 1.1.0          |
| SSL Certificate Provider | Let's Encrypt                         | N/A            |
| Jenkins Configuration    | Jenkins Configuration as Code Plugin  | 1.46           |
| Jenkins Credentials      | Jenkins Azure Key Vault Plugin        | 2.1            |

# Getting Started
## Requirements
### Azure resource requirements
* [An Azure subscription](https://docs.microsoft.com/en-us/azure/cost-management-billing/manage/create-subscription)
* An Azure Service Principal for Jenkins (hence known as the "Jenkins Service Principal") with permissions listed in the "Jenkins Service Principal Permissions"
* [An Azure Key Vault](https://azure.microsoft.com/en-ca/services/key-vault/)
* [An Azure Image Gallery](https://docs.microsoft.com/en-us/azure/virtual-machines/shared-image-galleries) containing images for VM agent deployments (if using VM Agents plugin)

### Jenkins Service Principal Permissions:
* Deployer (you) requires permission to modify the password of the Jenkins Service Principal
* Service Principal needs to have an access policy to allow the "get" and "list" permissions in the specified Key Vault
* Service Principal needs read-only access to Image Gallery specified in configuration/clouds.yml (if using VM Agents plugin)
* Service Principal needs contributor access to the VM Resource Group specified (if using VM Agents plugin), or you must manually create the resource group set for "AZURE_VM_RESOURCE_GROUP" and grant the Service Principal permissions directly on the resource group.

### Dependencies
#### Azure CLI
Used to run commands for Azure
https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
```
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```
#### Kubernetes CLI
Used to run commands for Kubernetes
https://kubernetes.io/docs/tasks/tools/install-kubectl/
```
KUBECTLVERSION=$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)
curl -LO https://storage.googleapis.com/kubernetes-release/release/${KUBECTLVERSION}/bin/linux/amd64/kubectl
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
kubectl version --client
```
#### Helm 3
Used to install Helm Charts for Jenkins ingress
https://helm.sh/docs/intro/install/
```
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | sudo bash
```

## Installation process
1. Open deploy_jenkins.sh and add in desired configuration. Detailed instructions are written in-script.
2. Create and ensure permissions are granted to the Jenkins Service Principal
3. Add executable permissions by running: `chmod +x deploy_jenkins.sh`
4. If not already done so, log in to Azure by running `az login` and follow the instructions
5. Install Jenkins plugins by running: `./deploy_jenkins.sh` and follow any prompts.
6. When deployment is complete, note down the password and url.
7. Visit the url and log in with the credentials noted down earlier.

#### Using Private Azure VM Agents
If using the Azure VM Agents plugin and you want to make the VMs private (e.g. not open to public), there is additional network configuration needed. Usually this is necessary if there are automated network security groups applied to your network adapters.

1. Note down the network range of your AKS cluster by viewing the Virtual Network's properties. Usually this is in the resource group that starts with "MC_" and ends with your AKS cluster name and region. 
2. Jenkins should create all the VM Agent resource groups and virtual networks when VM Agents is loaded. You can see this by browsing to the VM agent resource groups that are created.
3. Ensure the virtual network and subnet of every VM Agent resource group do not overlap with your AKS cluster and each other.
4. Peer each virtual network to your AKS cluster's virtual network. Ensure communication is allowed, and no gateway changes are necessary.
5. In configuration/clouds.yml, ensure that `usePrivateIP` is set to `true`, and that both `subnetName` and `virtualNetworkName` is set to the same value as you did for each VM Agent resource group.

If you are not using private IPs, ensure that in configuration/clouds.yml `usePrivateIP` is set to `false`, and that both `subnetName` and `virtualNetworkName` are not set (removed from the config).

# Upgrades and Maintenance

## Updating Jenkins Plugins
* For transient changes, it is recommended to update the plugins through the Jenkins UI. For any permanent you need to add it to the plugins list `plugins.txt`, and then run `./deploy_jenkins.sh -p` which will update the configmap `plugins`. For the new changes to take effect you will need to do a new rollout on Kubernetes to create new Jenkins masters for the changes to take effect. If you absolutely must use the same container then you can run `/bin/jenkins-plugin-cli --plugin-file /plugins/plugins.txt --plugin-download-directory /var/jenkins_home/plugins` inside the container.

## Updating Jenkins Configuration
1. Update `configuration/jenkins.yml` or if you want to keep it separate from core configuration you can add a new YAML file in `configuration/`.
2. Create a pull request into the master branch of openenclave/test-infra
3. Once merged, you may trigger a configuration reload by going to Jenkins > Manage Jenkins > Configuration as Code > Reload
4. If Jenkins cannot reload, there is likely an error with the configuration and the changes should be double checked and/or reverted.

_For more information, see https://github.com/jenkinsci/configuration-as-code-plugin_ 

### Creating new secrets
Note: You will need access to the AKS cluster to do this.
1. Ensure the new secrets or changes are appropriately added in deploy_jenkins.sh, configuration-update.sh, and kubernetes/configuration-update.yml 
2. Commit your changes and open a pull request into the master branch of openenclave/test-infra
3. Shortly before the pull request is merged, turn off configuration updates on Jenkins with `kubectl delete cronjob configuration-update`
4. Once merged, you can patch existing Jenkins with your changes by:
  1. Creating the secret manually
  2. Apply the new Kubernetes manifest
  3. Running `./deploy_jenkins.sh -c`
5. Continue by following the section on "Updating Jenkins Configuration" above, starting from step where a pull request is merged.

### Change value of existing secrets
Note: You will need access to the AKS cluster to do this.
1. Manually update the secret in the AKS Cluster.
2. Wait for a new configuration change to be checked in, or do a new rollout on Kubernetes to create new Jenkins masters.
3. Continue by following the section on "Updating Jenkins Configuration" above, starting from step where a pull request is merged.

### Updating configuration-update.sh
Note: You will need access to the AKS cluster to do this.
1. Make the desired updates and open a pull request into the master branch of openenclave/test-infra
2. Once merged, you can patch existing Jenkins with your changes by creating the secret manually, apply the new Kubernetes manifest, and run `./deploy_jenkins.sh -c`. The new changes will be used in the next configuration update.

### Upgrading Kubernetes version
Note: You will need access to the AKS cluster to do this.
1. Check the available Kubernetes versions
```
az aks show --resource-group myResourceGroup --name myAKSCluster --output table
```
2. See the release notes and deprecations for Kubernetes to ensure compatibility: https://kubernetes.io/docs/setup/release/
3. Upgrade your AKS cluster
```
az aks upgrade \
    --resource-group myResourceGroup \
    --name myAKSCluster \
    --kubernetes-version KUBERNETES_VERSION
```
_For more information, see https://docs.microsoft.com/en-us/azure/aks/upgrade-cluster_

## Updating Jenkins Jobs
1. Update the relevant job in `configuration/jobs/` or add your own job. The jobs shown in this directory uses the [job-dsl-plugin](https://plugins.jenkins.io/job-dsl/) which is usually made up of a combination of YAML, Groovy, Jenkins Pipeline syntax. For examples, see [the demos from Jenkins CasC](https://github.com/jenkinsci/configuration-as-code-plugin/tree/master/demos/jobs).
2. Continue by following the section on "Updating Jenkins Configuration", starting from step on creating a pull request.

_Job DSL API Reference: https://jenkinsci.github.io/job-dsl-plugin/_

Note: you cannot delete jobs by deleting the job DSL. You will have to delete the job DSL and the job in Jenkins.

## AKS Cluster Service Principal
The Service Principal used to create the AKS cluster will expire in 1 year. Before that expiry, you will need to update your AKS cluster with new credentials. Refer to this guide for more information: https://docs.microsoft.com/en-us/azure/aks/update-credentials

## SSL Certificate
The SSL certificates are managed by Jetstack's Cert Manager. Each certificate is valid for 3 months, and will be automatically renewed when within 1 month of expiry.

# Known Issues and Troubleshooting
## Service Principal issues
### Invalid secret for Service Principal
This is usually due to a delay with the Service Principal being propogated out within Azure. Open up deploy_jenkins.sh and manually replace `AKS_SP_ID` and `AKS_SP_SECRET` with corresponding values. For convenience you can find the values in the output of the last run of deploy_jenkins.sh.

## SSL Certificates
### Certificate not issued or valid
1. You can try to delete the certificate on the AKS Cluster, and let it be recreated: `kubectl delete certificate tls-secret`
2. You may have a misconfigured resource or you have hit Let's Encrypt's 50 certificate weekly limit.
  * Ensure Jenkins ingress has the correct domain with `kubectl describe jenkins-ingress`
  * Ensure Cert Manager services are running with `kubectl get pods -n ingress`
  * Check for errors with `kubectl describe certificaterequests` and equivalent commands for the `orders` and `challenge` resources.
  * Check for errors with https://letsdebug.net/


## Jenkins
### Plugins not initialized or missing
As Jenkins requires a reload after installing plugins, ensure that you are running on a new pod after plugins have been installed. If that is unsuccessful you can reinstall plugins by calling `./deploy_jenkins.sh -p`

# References
## Azure
* Azure Key Vault: https://docs.microsoft.com/en-us/azure/key-vault/
* Azure Kubernetes Service: https://docs.microsoft.com/en-us/azure/aks/

## Jenkins
* Jenkins LTS: https://www.jenkins.io/changelog-stable/
* Jenkins Configuration as Code: https://github.com/jenkinsci/configuration-as-code-plugin
* Jenkins Job DSL API Reference: https://jenkinsci.github.io/job-dsl-plugin/ 
