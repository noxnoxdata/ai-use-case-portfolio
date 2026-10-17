# Duplicate Use Case Report

Method: embeddings (nomic-embed-text). Threshold: 0.78.

Use cases: 14. Duplicate clusters: 5.

## Duplicate clusters

### Cluster 1 (2 use cases)

- **Policy Q&A Assistant** (1): Answer internal policy questions with citations.
- **Internal Policy Chatbot** (2): Answer questions about internal policies and cite the source.

### Cluster 2 (2 use cases)

- **KYC Document Extraction** (4): Extract fields from onboarding documents.
- **Onboarding Document Extraction** (5): Pull customer fields from KYC onboarding paperwork.

### Cluster 3 (2 use cases)

- **Complaint Triage** (6): Classify and route customer complaints.
- **Customer Complaint Routing** (7): Sort incoming complaints by topic and send to the right team.

### Cluster 4 (2 use cases)

- **Credit Memo Summarizer** (8): Summarise credit memos for reviewers.
- **Credit Memo Summary** (9): Condense credit memos into a short reviewer brief.

### Cluster 5 (2 use cases)

- **Churn Forecasting** (10): Predict which customers will leave.
- **Customer Churn Prediction** (11): Forecast customer attrition.

## Most similar pairs

| Use case A | Use case B | Similarity |
|---|---|---|
| KYC Document Extraction | Onboarding Document Extraction | 0.92 |
| Churn Forecasting | Customer Churn Prediction | 0.91 |
| Credit Memo Summarizer | Credit Memo Summary | 0.88 |
| Complaint Triage | Customer Complaint Routing | 0.86 |
| Policy Q&A Assistant | Internal Policy Chatbot | 0.82 |
| Policy Q&A Assistant | Ask Policy Documents | 0.75 |
| Onboarding Document Extraction | Contract Clause Extraction | 0.69 |
| KYC Document Extraction | Contract Clause Extraction | 0.67 |
| Internal Policy Chatbot | Ask Policy Documents | 0.65 |
| Customer Complaint Routing | Churn Forecasting | 0.63 |

Similarity is a signal, not a verdict. Read the top pairs before merging anything.