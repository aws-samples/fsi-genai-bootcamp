Lab Instructions
You will be using a Jupyter notebook in SageMaker created as part of the deployment.


Setup/Prerequisite
1.	Locate the SageMaker from the search menu and click on it. 

 

2.	Select Notebook from the left side panel and click on the dropdown and click on Notebook instances.
3.	Then click on Create notebook instance and a new page will open to create notebook instance. 
4.	Give the notebook instance name, leave the notebook instance type, elastic Inference and Platform identifier as default. 
5.	Under permissions and encryption click on the drop down icon to configure the IAM role and select create a new role.
 
6.	Leave the selected accesses as default and click on ‘create role’.
7.	Then click on create notebook instance. 
8.	Once the Status changed to InService, open the notebook instance to edit the IAM role and provide the necessary access to OpenSearch Serverless 

 

9.	Under Permissions and encryption click on the IAM role ARN. When you click on it, it will open a new tab and shows all the permissions policies attached to the role. 
10.	 Click on the dropdown button for the Add permissions and select Create inline policy. It will open a Specify permissions page. Choose OpenSearch serverless from the Service drop down. 
11.	 For this lab purpose provide full access by selecting all Opensearch serverless actions radio button and select all under Resources. Click on next, then give the policy a name and click on create policy. 
12.	Go back to your sageMaker Notebook instance and choose open Jupyter Notebook lab. 
Now Follow the Jupyter Notebook instruction and run the cell in sequence. Read the note on each cell code logic.


