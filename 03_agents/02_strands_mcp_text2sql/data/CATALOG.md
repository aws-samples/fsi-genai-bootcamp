# **Asset and Wealth Management Database Schema**

This document outlines the database schema for a typical asset and wealth management platform. The schema is designed to provide a comprehensive view of clients, their accounts, financial holdings, and transaction histories.

### **1\. Clients Table**

This table stores core demographic and profile information about each client. It serves as the central entity from which all other data is linked.

| Column Name | Data Type | Description | Example |
| :---- | :---- | :---- | :---- |
| client\_id | UUID | **Primary Key.** A unique identifier for the client. | c1a2b3c4-d5e6... |
| first\_name | String | The client's first name. | Jane |
| last\_name | String | The client's last name. | Doe |
| email | String | The client's primary email address. | jane.doe@email.com |
| phone\_number | String | The client's contact phone number. | (555) 123-4567 |
| date\_of\_birth | Date | The client's date of birth. | 1975-05-20 |
| risk\_profile | String | The client's investment risk tolerance. | Aggressive |
| investment\_objective | String | The primary goal for the client's portfolio. | Growth |
| created\_at | Timestamp | The timestamp when the client record was created. | 2020-01-15 09:30:00 |

### **2\. Accounts Table**

This table details the various investment accounts that belong to each client.

| Column Name | Data Type | Description | Example |
| :---- | :---- | :---- | :---- |
| account\_id | UUID | **Primary Key.** A unique identifier for the account. | acc\_9f8e7d6c... |
| client\_id | UUID | **Foreign Key.** Links to the Clients table. | c1a2b3c4-d5e6... |
| account\_type | String | The type of investment account. | Taxable Brokerage |
| account\_name | String | A user-friendly name for the account. | J. Doe Retirement |
| currency | String | The base currency of the account. | USD |
| inception\_date | Date | The date the account was opened. | 2020-02-01 |
| status | String | The current status of the account. | Active |

### **3\. Holdings Table**

This table provides a snapshot of the specific assets (e.g., stocks, bonds, ETFs) held within each account.

| Column Name | Data Type | Description | Example |
| :---- | :---- | :---- | :---- |
| holding\_id | UUID | **Primary Key.** A unique ID for the holding record. | hld\_a1b2c3d4... |
| account\_id | UUID | **Foreign Key.** Links to the Accounts table. | acc\_9f8e7d6c... |
| ticker\_symbol | String | The market symbol for the asset (e.g., AAPL, GOOGL). | AAPL |
| asset\_name | String | The full name of the asset. | Apple Inc. |
| asset\_class | String | The classification of the asset (e.g., Equity). | Equity |
| quantity | Decimal | The number of shares or units held. | 150.75 |
| cost\_basis | Decimal | The original value of the holding for tax purposes. | 15100.50 |
| market\_value | Decimal | The current market value of the holding. | 28500.00 |
| last\_updated | Timestamp | The timestamp of the last market value update. | 2025-06-16 16:00:00 |

### **4\. Transactions Table**

This table logs all financial activities, including buys, sells, deposits, and dividends, that occur within an account.

| Column Name | Data Type | Description | Example |
| :---- | :---- | :---- | :---- |
| transaction\_id | UUID | **Primary Key.** A unique ID for the transaction. | txn\_1a2b3c4d... |
| account\_id | UUID | **Foreign Key.** Links to the Accounts table. | acc\_9f8e7d6c... |
| ticker\_symbol | String | The symbol of the asset involved (if applicable). | NVDA |
| transaction\_type | String | The nature of the transaction (e.g., Buy, Sell). | Buy |
| trade\_date | Date | The date the transaction was executed. | 2024-11-10 |
| settlement\_date | Date | The date the transaction officially settled. | 2024-11-12 |
| quantity | Decimal | The number of units transacted. | 20 |
| price | Decimal | The price per unit for the transaction. | 310.45 |
| net\_amount | Decimal | The total value of the transaction. | 6209.00 |

