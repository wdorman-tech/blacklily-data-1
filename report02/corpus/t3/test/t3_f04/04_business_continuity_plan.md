# Business Continuity Plan

**Wrenholt Pryce Asset Management LLC**

Version 7.0, revised December 1, 2025
Plan owner: Dmitri Halloway, Chief Operating Officer

> **SYNTHETIC DOCUMENT: FOR BENCHMARK USE ONLY.** This document is fictional. Wrenholt Pryce Asset Management LLC, Wrenholt Pryce Long Duration Credit Fund, L.P. and all persons, service providers and figures named herein are invented for the purpose of evaluating document-processing systems. It is not an offer to sell securities and does not describe any real entity.

## SECTION 1. PLAN OWNERSHIP AND GOVERNANCE

### 1.1 Plan Owner

The Chief Operating Officer, Dmitri Halloway, is the owner of this Plan and is responsible for its maintenance, testing and activation. Aurelia Pennock, Business Continuity Coordinator (the "Coordinator"), maintains the Plan documents, emergency contact lists and vendor recovery information, and coordinates each test and exercise.

### 1.2 Crisis Management Team

The Crisis Management Team is led by the Chief Operating Officer and consists of the Chief Executive Officer, Colette Varnum; the Chief Investment Officer, Tobias Aldren; the Chief Financial Officer, Ines Morrow-Tate; the Chief Compliance Officer, Priya Castellane; the Chief Technology Officer and Information Security Officer, Samuel Treloar; and the Head of Trading, Marcus Ebbing. Each member has a designated alternate recorded in the emergency contact list maintained by the Coordinator.

### 1.3 Declaration

A business disruption may be declared by the Chief Executive Officer or the Chief Operating Officer or, if neither can be reached within 30 minutes, by any two members of the Crisis Management Team. Recovery time objectives in Section 3 are measured from the time of declaration.

### 1.4 Review and Approval

The Plan owner reviews the Plan at least annually and after any material change in the Firm's business, systems, vendors or premises. Revisions are approved by the Management Committee. The Chief Compliance Officer reviews the Plan as part of the annual compliance review.

## SECTION 2. ALTERNATE SITE AND REMOTE OPERATIONS

### 2.1 Alternate Site

The Firm's alternate site is a dedicated recovery suite operated by Norcastle Recovery Services in Glastonbury, Connecticut, approximately eight miles from the Firm's Hartford office. The suite is reserved exclusively for the Firm, is accessible 24 hours a day, and provides 20 pre-configured workstations, including six trading positions with market data and dealer connectivity. The Coordinator verifies the suite's equipment and network connections monthly.

### 2.2 Remote Operations

Every employee is issued a Firm laptop configured for secure remote access through the Firm's virtual private network with multi-factor authentication. All critical functions, including trading, can be performed remotely. The alternate site is used for functions that benefit from co-location, principally the trading desk, Portfolio Operations and technology support, and for employees who cannot work effectively from home.

### 2.3 Data Centers

The Firm's hosted systems, including its portfolio accounting platform, file shares and internal applications, run in a colocation facility in Windsor, Connecticut operated by Tullborne Data Centers. The order management system is provided as a hosted service by Pelloran Systems, which maintains its own recovery environment. Email is provided through a cloud service and captured by Kestle Archive Services.

## SECTION 3. RECOVERY OBJECTIVES

### 3.1 Recovery Time and Recovery Point Objectives

| System or function | Recovery time objective | Recovery point objective |
|---|---|---|
| Order management, trading platforms and market data | 4 hours | 15 minutes |
| Portfolio accounting, cash management and reconciliation | 8 hours | 15 minutes |
| Email and archived messaging | 6 hours | 1 hour |
| Pricing feeds and valuation tools | 8 hours | 24 hours |
| File shares, research and internal applications | 24 hours | 15 minutes |
| Client reporting and fee billing | 2 business days | 24 hours |

The Firm's most critical objective is the restoration of order management, trading platforms and market data within four hours of declaration, so that portfolio managers can meet client cash flow needs and manage risk during the trading day.

### 3.2 Prioritization

Tier 1 functions are trading, cash management and trade settlement. Tier 2 functions are pricing, portfolio accounting and compliance monitoring. Tier 3 functions are client reporting, fee billing and marketing. Recovery resources are applied in tier order.

## SECTION 4. CRITICAL VENDORS

### 4.1 Critical Vendor List

| Vendor | Service |
|---|---|
| Pelloran Systems | Hosted order management system |
| Lanthorn Evaluated Pricing, Inc. | Primary pricing service |
| Brayford Pricing Data LLC | Secondary pricing service |
| Quillfield Fund Services LLC | Commingled Fund administration |
| Ostrander Keel Trust Company, N.A. | Commingled Fund custody |
| Tullborne Data Centers | Primary colocation facility, Windsor, Connecticut |
| Ferrowby Cloud Backup, Inc. | Replication, backup and recovery environment |
| Norcastle Recovery Services | Alternate site, Glastonbury, Connecticut |
| Grisby Lane Security | Managed security services and security operations center |
| Kestle Archive Services | Email and messaging archive |
| Callowmere Notify | Emergency mass notification |

Separate account custodians are selected by clients and are not Firm vendors, but the Coordinator maintains emergency contacts for each custodian.

### 4.2 Vendor Oversight

Each critical vendor must provide a summary of its business continuity plan and its most recent SOC 1 or SOC 2 report annually. The Coordinator reviews these materials, and the Plan owner reviews any exception, including any vendor recovery time commitment that is longer than the Firm's objective for the related function.

## SECTION 5. DATA BACKUP

### 5.1 Replication

Systems hosted in the Windsor facility are replicated to the Ferrowby Cloud Backup recovery environment every 15 minutes. In a disruption affecting the Windsor facility, the Chief Technology Officer directs failover to that environment.

### 5.2 Backup Frequency, Location and Retention

Nightly immutable backups of all Firm-hosted systems, cloud email and cloud document storage are taken at 11:00 p.m. Eastern time and written to Ferrowby Cloud Backup data centers in Columbus, Ohio and Hillsboro, Oregon. Backups are encrypted using AES-256 and cannot be altered or deleted during their retention period. Nightly backups are retained for 35 days, weekly backups for 13 months, and month-end backups for seven years.

### 5.3 Restoration Checks

Technology staff restore a sample of files and one complete system from backup each quarter and document the results, including the time required.

## SECTION 6. TESTING

### 6.1 Testing Program

The Firm conducts a full test of the Plan annually, in the fourth quarter, including relocation of trading and operations staff to the alternate site, remote operation by all other staff, and failover of the Windsor systems to the Ferrowby Cloud Backup recovery environment. Tabletop exercises are conducted semi-annually, at least one of which addresses a cyber incident. The call tree is tested quarterly.

### 6.2 Most Recent Full Test

The most recent full test was conducted on Saturday, October 18, 2025. Twelve employees operated from the alternate site and the remainder worked remotely, and the Windsor systems were failed over to the recovery environment and restored. All critical systems were restored within their recovery time objectives. The test identified one issue: market data entitlements at the alternate site had not been updated for two traders hired in 2025. The entitlements were corrected in November 2025, and the Coordinator now confirms entitlements monthly.

### 6.3 Other Exercises

The most recent tabletop exercise, held in June 2025, simulated a ransomware attack affecting the Windsor facility and included Grisby Lane Security and Quenby Digital Forensics LLC. In the call tree test conducted in September 2025, all but two employees acknowledged the notification within the required 30 minutes; both were reached by their department heads.

### 6.4 Reporting

Results of each test and exercise are reported in writing to the Management Committee and the Chief Compliance Officer, and remediation items are tracked by the Coordinator until closed.

## SECTION 7. COMMUNICATION TREE

### 7.1 Initial Notification

On declaration of a business disruption, the Coordinator sends an emergency notification to all employees through Callowmere Notify by text message, voice call and email. Each employee must acknowledge the notification within 30 minutes.

### 7.2 Call Tree

The Chief Operating Officer notifies the Crisis Management Team. Each member then notifies the department heads for which the member is responsible: the Chief Executive Officer notifies the Management Committee and client service; the Chief Investment Officer notifies portfolio management and credit research; the Head of Trading notifies the trading desk; the Chief Financial Officer notifies finance and Portfolio Operations; the Chief Technology Officer notifies technology staff; and the Chief Compliance Officer notifies compliance staff and outside counsel. Department heads call any employee who has not acknowledged the initial notification.

### 7.3 External Communications

Client service notifies separate account clients and Commingled Fund investors whose services are affected by the end of the business day on which the disruption is declared. Portfolio Operations notifies custodians, Quillfield Fund Services LLC and key dealers. The Chief Compliance Officer determines whether any regulatory notification is required. Only the Chief Executive Officer may speak to the media.

## SECTION 8. PANDEMIC AND PUBLIC HEALTH EVENTS

### 8.1 Phased Response

In Phase 1 (monitoring), the Crisis Management Team monitors public health guidance and confirms that all employees can work remotely. In Phase 2 (split operations), the trading desk and Portfolio Operations are divided into two teams that alternate weekly between the Hartford office and remote or alternate site operation, so that the teams do not share premises. In Phase 3 (full remote), all employees work remotely and the office is closed except for essential access approved by the Chief Operating Officer.

### 8.2 Minimum Staffing

Each business day the Firm must have available at least two traders, one portfolio manager for each strategy and two Portfolio Operations analysts. Cross-training records maintained by department heads identify the employees qualified to perform each critical function.

## SECTION 9. CYBER INCIDENT RESPONSE

### 9.1 Incident Response Team

The Incident Response Team is led by the Information Security Officer and includes the Chief Operating Officer, the Chief Compliance Officer, the Chief Financial Officer and the manager of technology operations. Outside counsel joins the team for any incident that may involve unauthorized access to client or personal information.

### 9.2 Detection and Escalation

Grisby Lane Security monitors the Firm's systems 24 hours a day and escalates any Severity 1 incident, meaning an incident that affects trading, client data or the integrity of Firm systems, to the Information Security Officer by telephone within 15 minutes of detection. Severity 2 and Severity 3 incidents are escalated through the managed security ticketing system.

### 9.3 Outside Advisers

Quenby Digital Forensics LLC is retained to provide forensic investigation services. Dunmore Achterberg LLP serves as outside counsel for cyber incidents and engages the forensic firm where appropriate so that its work is performed at the direction of counsel.

### 9.4 Containment and Recovery

The Incident Response Team isolates affected systems, preserves evidence and restores systems from immutable backups under Section 5 after the Information Security Officer confirms that the backups are free of compromise. No ransom may be paid without the approval of the Management Committee after consultation with outside counsel and notification of law enforcement.

### 9.5 Notifications

The Chief Compliance Officer determines what notifications are required to clients, regulators and affected individuals, including notifications under the privacy provisions of the Compliance Manual. The Chief Financial Officer notifies the Firm's cyber liability insurer in accordance with the terms of the policy.
