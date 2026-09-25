# Business Continuity and Disaster Recovery Plan

**Tennick Arlow Wealth Partners, LLC**

**Version 5.2, revised May 4, 2026**

> **SYNTHETIC DOCUMENT: FOR BENCHMARK USE ONLY.** This document is fictional. Tennick Arlow Wealth Partners, LLC and all persons, service providers and figures named herein are invented for the purpose of evaluating document-processing systems. It is not an offer to sell securities and does not describe any real entity.

## SECTION 1. PURPOSE, SCOPE AND ASSUMPTIONS

### 1.1 Purpose

This Business Continuity and Disaster Recovery Plan (the "Plan") describes how Tennick Arlow Wealth Partners, LLC (the "Firm") will continue to meet its obligations to clients during and after a Significant Business Disruption. As a fiduciary, the Firm must be able to protect client information, maintain access to client accounts and continue to manage client portfolios when its offices, systems, personnel or vendors are unavailable.

### 1.2 Scope

The Plan covers the Firm's three offices, in Richmond, Virginia (the principal office), Charlottesville, Virginia and Raleigh, North Carolina, all Supervised Persons, and the systems and vendors listed in Section 3 and Section 5. Client assets are held by unaffiliated qualified custodians, which maintain their own business continuity plans. A disruption at the Firm does not prevent clients from contacting their custodian directly to obtain account information or to request withdrawals.

### 1.3 Significant Business Disruption

A Significant Business Disruption is any event that prevents the Firm from operating one or more offices or critical systems in the normal course, including loss of an office through fire, flood or utility failure, a regional disaster, a public health emergency, a cybersecurity incident, the loss of a critical vendor, or the unavailability of key personnel.

## SECTION 2. PLAN OWNERSHIP AND GOVERNANCE

### 2.1 Plan Owner

Harriet Solberg, Chief Operating Officer, is the owner of this Plan. The Plan Owner is responsible for maintaining the Plan, for declaring a Significant Business Disruption and for directing the Firm's response. Owen Stahlberg, Director of Technology, serves as BCP Coordinator and is responsible for the technical recovery procedures, for vendor recovery arrangements and for organizing the tests described in Section 7.

### 2.2 Approval and Review

The Management Committee approves the Plan and each material amendment. The Plan Owner reviews the Plan at least annually, after each activation and after each test, and whenever the Firm opens an office, changes a critical vendor or adopts a new critical system. The Chief Compliance Officer reviews the Plan as part of the annual compliance review.

### 2.3 Declaration and Delegation of Authority

The Plan Owner declares a Significant Business Disruption and activates the Plan. If the Plan Owner is unavailable, the Chief Financial Officer may declare a Significant Business Disruption and exercise the Plan Owner's authority under the Plan, and if both are unavailable, the Managing Partner may do so.

## SECTION 3. RECOVERY OBJECTIVES

### 3.1 Recovery Time Objectives

The Firm classifies its systems in three tiers according to their importance to clients. Tier 1 systems are the order management and trading system, access to the custodians' advisor platforms, the portfolio accounting system and the Firm's email and telephone systems. The recovery time objective for Tier 1 systems is 24 hours from the declaration of a Significant Business Disruption. Tier 2 systems are the client relationship management system, the financial planning software, the document management system and the billing module of the portfolio accounting system; their recovery time objective is 48 hours. Tier 3 systems are all other systems, including the public website and internal collaboration tools; their recovery time objective is five business days.

### 3.2 Manual Workarounds

Until a Tier 1 system is recovered, traders may place orders directly through the custodians' advisor platforms or by telephone to the custodians' trading desks, and portfolio managers may use custodian holdings reports in place of the portfolio accounting system. Manual orders are logged and reconciled once the order management system is restored.

## SECTION 4. ALTERNATE SITES AND REMOTE WORK

### 4.1 Alternate Sites

If the Richmond office is unavailable, the Charlottesville office serves as the primary alternate site for trading, operations and client service. If both the Richmond and Charlottesville offices are unavailable, the Raleigh office serves as the secondary alternate site. If the Charlottesville or Raleigh office is unavailable, its personnel work from the Richmond office or remotely. Each office maintains workstations, network connections and printers configured for use by personnel from the other offices.

### 4.2 Remote Work

Every Supervised Person is issued a Firm-managed laptop and may work remotely through the Firm's secure remote access service, which requires multi-factor authentication. All Tier 1 and Tier 2 systems are accessible remotely. Traders keep Firm-managed mobile devices with approved access to the custodians' advisor platforms.

### 4.3 Physical Records

The Firm keeps few physical records. Original documents that must be kept in paper form, such as executed trust instruments delivered by clients, are scanned into the document management system on receipt and the originals are stored in fire-resistant cabinets in the Richmond office.

## SECTION 5. CRITICAL VENDORS

### 5.1 Vendor Oversight

The Plan Owner and the BCP Coordinator maintain a list of critical vendors, obtain each vendor's business continuity summary and, where available, its most recent independent controls report, and review them annually as part of the vendor due diligence required by the Compliance Manual.

### 5.2 Critical Vendor List

| Vendor | Service |
|---|---|
| Harlowe Crest Securities, LLC | Custody, execution and advisor platform |
| Brindlemoor Trust Company, N.A. | Custody of trust and certain retirement accounts |
| Tessaline Portfolio Systems, Inc. | Portfolio accounting, performance reporting and billing |
| Norcastle Managed Services, LLC | Managed IT services, cloud hosting and data backup |
| Marrowgate Archiving, Inc. | Archiving of electronic communications |
| Ashcombe Pricing Data, LLC | Secondary pricing source |
| Veridane Proxy Services, Inc. | Proxy research, vote execution and records |
| Kettleby Compliance Systems, Inc. | Compliance platform |

For each critical vendor, the BCP Coordinator maintains primary and after-hours contacts and the vendor's commitments for restoring service to the Firm.

## SECTION 6. DATA BACKUP AND RECOVERY

### 6.1 Backup Frequency

Norcastle performs incremental backups of the Firm's file server and document management system every four hours between 6:00 a.m. and 10:00 p.m. Eastern time on business days, and a full backup every night. Cloud applications provided by Tessaline and the Firm's client relationship management provider are backed up by those providers under their own controls, which the BCP Coordinator reviews annually.

### 6.2 Storage Location and Retention

Backup copies are replicated to Norcastle's secondary data center in Columbus, Ohio, more than 300 miles from each Firm office. Nightly backups are held in immutable storage for 35 days, and a monthly full backup is retained for 12 months.

### 6.3 Restoration Testing

Norcastle restores a sample of files and one full system image from backup each quarter. The BCP Coordinator reviews the results and records any failure and its remediation.

## SECTION 7. TESTING AND TRAINING

### 7.1 Testing Frequency and Most Recent Test

The Plan is tested at least annually. The most recent full test of the Plan was conducted on October 22, 2025. It combined a tabletop exercise, based on a scenario in which the Richmond office was closed by a regional power outage, with a live exercise in which the trading desk operated from the Charlottesville office and all other personnel worked remotely for a full business day. The results were reported to the Management Committee on November 12, 2025. The next full test is scheduled for October 2026.

### 7.2 Follow-Up

The BCP Coordinator records each issue identified in a test, assigns an owner and a completion date, and reports open items to the Plan Owner monthly until they are resolved.

### 7.3 Training

Each Supervised Person receives training on the Plan when joining the Firm and annually, including the use of remote access, the communication procedures in Section 8 and his or her role during a Significant Business Disruption.

## SECTION 8. COMMUNICATION TREE

### 8.1 Activation

When the Plan is activated, the Plan Owner, or the person exercising the Plan Owner's authority under Section 2.3, sends an alert to all Supervised Persons through the Firm's mass notification service by text message, voice call and email. Each Supervised Person must acknowledge the alert within 60 minutes.

### 8.2 Internal Tree

The Plan Owner contacts the other members of the Management Committee, the Chief Compliance Officer, the BCP Coordinator, the Head of Trading, and the Managing Directors of the Charlottesville and Raleigh offices, Everett Linwood and Camille Dubrow. Each of them contacts the personnel who report to them and confirms their status and location. Any Supervised Person who has not been reached within two hours is reported to the Plan Owner, who directs further efforts to make contact.

### 8.3 External Communications

The Firm informs clients of a Significant Business Disruption through a notice on its website and by email, and wealth advisors contact affected households directly by telephone where a disruption is expected to last more than one business day. The Head of Trading and the BCP Coordinator notify the custodians and critical vendors. The Chief Compliance Officer determines whether any notice to a regulator is required. Only the Managing Partner, or a person she designates, may speak to the media.

## SECTION 9. PANDEMIC AND PUBLIC HEALTH EVENTS

### 9.1 Response

During a pandemic or other public health emergency, the Plan Owner may direct some or all personnel to work remotely, may divide the trading and operations teams between the Richmond and Charlottesville offices so that no single exposure disables either function, and may suspend in-person client meetings. Each critical function has at least one cross-trained backup, and the Plan Owner reviews backup coverage when absences increase. Personnel who are ill are expected to remain at home and notify their supervisor.

## SECTION 10. CYBER INCIDENT RESPONSE

### 10.1 Incident Response Team

The Incident Response Team is led by the Information Security Officer, Owen Stahlberg, and includes the Chief Operating Officer, the Chief Compliance Officer and the Firm's outside counsel, Garrow Whitcombe LLP. The Information Security Officer may engage a forensic investigation firm through counsel, including a firm approved under the Firm's cyber liability insurance policy.

### 10.2 Response Phases

The Incident Response Team identifies and contains the incident, preserves evidence, eradicates the cause and restores affected systems from clean backups. Where client account credentials or client information may have been compromised, the Team notifies the custodians immediately so that they can place alerts on the affected accounts. The Chief Compliance Officer is responsible for notifications to affected individuals and regulators under the Compliance Manual.

### 10.3 Ransomware

No ransom or extortion payment may be made without the approval of the Management Committee after consultation with outside counsel and law enforcement. The Firm's priority in a ransomware event is to restore systems from backups held in immutable storage.

## SECTION 11. PLAN MAINTENANCE

### 11.1 Contact Lists and Records

The BCP Coordinator updates personnel and vendor contact lists quarterly and after any change in personnel. Copies of the Plan and the contact lists are kept in the document management system, on each Management Committee member's Firm-managed mobile device and in printed form at each office.
