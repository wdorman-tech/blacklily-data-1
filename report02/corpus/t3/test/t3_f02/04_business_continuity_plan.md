# Business Continuity Plan

**Sallowmere Capital Management, LP**

Version date: February 9, 2026

> **SYNTHETIC DOCUMENT: FOR BENCHMARK USE ONLY.** This document is fictional. Sallowmere Capital Management, LP, Sallowmere Partners Fund, LP, Sallowmere Partners Offshore Fund, Ltd., Sallowmere Co-Investment Fund I, LP and all persons, service providers and figures named herein are invented for the purpose of evaluating document-processing systems. It is not an offer to sell securities and does not describe any real entity.

## SECTION 1. PURPOSE AND SCOPE

### 1.1 Purpose

This Business Continuity Plan (the "Plan") sets out how Sallowmere Capital Management, LP (the "Adviser") will continue to manage Sallowmere Partners Fund, LP, Sallowmere Partners Offshore Fund, Ltd. and Sallowmere Co-Investment Fund I, LP (the "Funds"), protect investor assets and data, and meet its regulatory obligations during and after a significant business disruption ("SBD"). An SBD includes loss of access to the Adviser's office at 412 Atlantic Street, Stamford, Connecticut, a regional power or telecommunications failure, a severe weather event, a pandemic, the failure of a critical vendor, and a cybersecurity incident.

### 1.2 Scope

The Plan covers all personnel, systems and critical vendors of the Adviser. It is adopted under Section 1.3 of the Compliance Manual, and its incident response provisions are incorporated by reference in Section 11.5 of the Compliance Manual.

## SECTION 2. PLAN GOVERNANCE

### 2.1 Plan Owner

The President and Chief Operating Officer, Mireille Dansby, is the owner of the Plan and is accountable for its maintenance, resourcing and execution.

### 2.2 BCP Coordinator

The Director of Technology, Kofi Brannigan, serves as BCP Coordinator. The BCP Coordinator maintains the Plan documentation, the recovery runbooks for each system, the critical vendor contact list and the communication tree, and organizes all exercises under Section 7.

### 2.3 Declaration Authority

The President and Chief Operating Officer declares an SBD and activates the Plan. If she is unavailable, the Chief Financial Officer, Oren Pellisier, may declare an SBD. The person declaring the SBD records the time of declaration and the recovery tier activated, and notifies the Management Committee.

### 2.4 Approval and Review

The Plan is approved by the Management Committee and reviewed at least annually by the Plan owner, and after every activation or exercise. The Chief Compliance Officer reviews the Plan as part of the annual compliance review.

## SECTION 3. ALTERNATE SITE AND REMOTE OPERATIONS

### 3.1 Alternate Site

The Adviser subscribes to a workspace recovery facility in Norwalk, Connecticut, operated by Ravensholt Recovery Services LLC. The subscription provides eight dedicated seats, including two trading positions with dual market data displays and recorded telephone lines, available within four hours of the Adviser's declaration of an SBD. The facility has independent power, generator backup and diverse telecommunications carriers. The Head of Trading, the execution trader, the Chief Investment Officer, the Controller and the BCP Coordinator are assigned seats at the alternate site, with the remaining seats allocated by the Plan owner.

### 3.2 Remote Operations

Every employee is issued a firm laptop configured for secure remote access through the Adviser's virtual private network and virtual desktop environment, with multi-factor authentication. The order management system and the prime broker trading and reporting portals are accessible remotely. If the alternate site is unavailable or inaccessible, the Adviser operates entirely remotely. Traders working remotely use the recorded softphone application, and all business communications remain subject to Section 14 of the Compliance Manual.

## SECTION 4. RECOVERY OBJECTIVES

### 4.1 Recovery Tiers

Each system is assigned to a recovery tier with a recovery time objective ("RTO") and a recovery point objective ("RPO"):

| Tier | Systems and functions | RTO | RPO |
|---|---|---|---|
| Tier 1 | Order management and execution, prime broker connectivity, market data, risk reporting | 4 hours | 15 minutes |
| Tier 2 | Email and approved messaging, file storage, portfolio accounting and reconciliation | 8 hours | 1 hour |
| Tier 3 | Research databases, investor relations systems, human resources and other administrative systems | 48 hours | 24 hours |

### 4.2 Trading Continuity

If Tier 1 systems cannot be restored within the RTO, the Head of Trading may place orders by recorded telephone directly with the trading desks of the prime brokers and approved executing brokers. Orders placed by telephone are entered into the order management system as soon as it is restored and are reviewed by the Chief Compliance Officer.

## SECTION 5. CRITICAL VENDORS

### 5.1 Critical Vendor List

The following vendors are designated critical, and their contact details, escalation paths and contractual recovery commitments are maintained by the BCP Coordinator:

- Carvell Brink Fund Services Ltd., administrator to each Fund.
- Brisworth Tallent Securities LLC, primary prime broker, and Quarrington Prime Services LLC, second prime broker.
- Tellwright Systems, Inc., provider of the vendor-hosted order and execution management system.
- Orrisdale Market Data LLC and Pennick Pricing Services Inc., pricing and market data vendors.
- Quillon Archive Services, Inc., electronic communications archiving.
- Ravensholt Recovery Services LLC, workspace recovery facility.
- The IT managed service provider described in Section 5.2.

### 5.2 IT Managed Service Provider

Oskerby Technology Group LLC serves as the Adviser's IT managed service provider. Oskerby provides help desk support, endpoint management, network monitoring and administration of the Adviser's cloud environment and backup platform, and maintains a 24-hour security operations function that escalates alerts to the BCP Coordinator. Oskerby's service agreement commits to a one-hour response to any incident the Adviser classifies as critical.

### 5.3 Vendor Continuity Review

As part of the annual vendor due diligence described in Section 11.4 of the Compliance Manual, the BCP Coordinator obtains and reviews each critical vendor's business continuity summary and most recent independent control report, confirms its recovery commitments are consistent with the tiers in Section 4.1, and documents any gap and the Adviser's mitigation.

## SECTION 6. DATA BACKUP AND RECOVERY

### 6.1 Backup Frequency

The Adviser's file storage, email and portfolio accounting data are backed up through a third-party immutable backup platform administered by the IT managed service provider. Hourly incremental snapshots are taken during each business day, and a full backup is taken nightly at 11:00 p.m. Eastern Time. The order management system and market data are hosted by their vendors, whose backup arrangements are reviewed under Section 5.3.

### 6.2 Storage Locations and Retention

Backup copies are encrypted in transit and at rest and are stored in two geographically separate data centers in Ashburn, Virginia and Columbus, Ohio, neither of which is located within 100 miles of the Adviser's office. Daily backups are retained for 35 days, and month-end backups are retained for seven years consistent with Section 13.2 of the Compliance Manual. Backup copies are immutable and cannot be altered or deleted by any Adviser or vendor account during the retention period.

### 6.3 Restore Verification

The IT managed service provider restores a sample of files, mailboxes and the portfolio accounting database from backup each quarter and reports the results, including restore times, to the BCP Coordinator.

## SECTION 7. TESTING

### 7.1 Frequency

The Plan is tested through a full exercise at least annually, including relocation of the designated personnel to the alternate site for a full trading day and restoration of Tier 1 and Tier 2 systems, and through a call tree exercise every six months. The BCP Coordinator also conducts an annual tabletop exercise of the cyber incident response procedures in Section 9.2 with the Incident Response Team.

### 7.2 Most Recent Exercises

The most recent full exercise was conducted on November 14, 2025. Six employees operated from the Norwalk alternate site for the full trading day, the remaining employees worked remotely, and all Tier 1 systems were available within the four-hour RTO. The exercise identified a delay in activating the recorded softphone licenses, which was remediated in December 2025. The most recent call tree exercise was conducted on January 22, 2026. Results of each exercise are reported in writing to the Management Committee.

## SECTION 8. COMMUNICATION TREE

### 8.1 Internal Communications

On declaration of an SBD, the Plan owner notifies the Management Committee and the department heads through the Adviser's mass notification application, followed by telephone. Each department head then contacts every member of his or her team. Every employee must acknowledge the notification within 30 minutes and confirm his or her location and ability to work. The BCP Coordinator tracks acknowledgments and follows up on any employee who has not responded.

### 8.2 Investors, Counterparties and Service Providers

The Head of Investor Relations, Celia Brandvold, coordinates communications with investors, in consultation with the Plan owner and the Chief Compliance Officer, and with the Administrator where investor dealing may be affected. The Head of Trading notifies the prime brokers and executing brokers of any change in trading locations or authorized contacts. The Chief Financial Officer notifies the Administrator of any expected delay in pricing or reconciliation.

### 8.3 Regulators

The Chief Compliance Officer determines whether any notice to the SEC, the Cayman Islands Monetary Authority or any other regulator is required and makes any required notice.

## SECTION 9. PANDEMIC AND CYBER INCIDENT RESPONSE

### 9.1 Pandemic Response

The Plan owner may activate the following phases in response to a public health emergency. In Phase 1 (monitoring), the Adviser reviews public health guidance, restricts non-essential travel and confirms remote access for all employees. In Phase 2 (split operations), the Adviser divides critical functions into two teams that do not occupy the office on the same days, and the Head of Trading and the execution trader work from separate locations at all times. In Phase 3 (full remote), the office is closed and all employees work remotely or from the alternate site. The Plan owner determines the timing of any return to the office.

### 9.2 Cyber Incident Response

The Incident Response Team is led by the Director of Technology, acting as Information Security Officer, and includes the Chief Compliance Officer, the President and Chief Operating Officer, a representative of the IT managed service provider and, as needed, outside counsel and a forensic investigation firm. On detection of a suspected incident, the Incident Response Team classifies its severity, contains the incident by isolating affected systems and disabling compromised credentials, preserves evidence, and eradicates the threat before systems are restored from clean backups. The Chief Compliance Officer determines whether notification is required to investors, affected individuals, regulators or law enforcement, and any notification to affected individuals is made within the deadlines set out in Section 12.3 of the Compliance Manual. The President and Chief Operating Officer notifies the carrier under the Adviser's cyber liability insurance policy. After each incident, the Incident Response Team documents the root cause and remediation and reports to the Management Committee.

### 9.3 Temporary Delegation of Trading Authority

If the Chief Investment Officer is unable to perform his duties during an SBD, the Head of Risk and the most senior sector analyst available may jointly authorize trades necessary to reduce risk, meet margin calls or maintain compliance with the portfolio guidelines, but may not initiate new positions. The delegation ends when the Chief Investment Officer resumes his duties or the Management Committee determines otherwise.
