# Product Requirements Document (PRD)
**Product Name:** Clevercolab Classifier: Logistics Document Organizer (Working Title)
**Document Version:** 2.0
**Target Industry:** International Transport Logistics / Customs Agency (Agencia de Aduanas, Chile)

## 1. Product Overview
### 1.1 Objective
To automate the classification, splitting, organization, and **consistency validation** of international logistics documents. The system will process incoming files, identify document types, extract key reference IDs, separate merged documents, verify that all documents belong to the same shipment, and return a clean, properly named package to the user.

### 1.2 Problem Statement
Customs agencies process high volumes of client documents that are often poorly named, merged into massive single PDFs, and disorganized. Furthermore, clients sometimes accidentally include documents from different shipments in the same batch. Manually reviewing, separating, renaming, and cross-checking these documents is highly inefficient and risks costly errors during the *despacho aduanero* (customs clearance) process.

## 2. User Roles
*   **Client / End User:** Uploads files to the web application (and in later phases, via email) to have their shipment packages organized and verified.
*   **Operations Executive (Agencia de Aduanas):** Uses the output to quickly proceed with customs declarations.
*   **System Administrator:** Manages the expected document list, monitors system health, and handles edge cases.

## 3. Supported Document Types & Descriptions
The system must recognize and classify the following core documents. Descriptions and Chilean-specific requirements are detailed below:

### 3.1 Core International Documents
1.  **Documento de Transporte / Transport Document (BL, CRT, AWB):** 
    *   *Description:* The core contract of carriage and receipt of goods (Bill of Lading for sea, Carta de Porte Terrestre for land, Air Waybill for air). 
    *   *Rule:* **Primary Document.** The system must extract the unique Transport ID (e.g., BL number). This ID dictates the normalization of all other files in the batch.
2.  **Factura Comercial (Commercial Invoice):** 
    *   *Description:* The legal bill of sale detailing the buyer, seller, goods, quantities, and prices.
3.  **Lista de Empaque (Packing List):** 
    *   *Description:* Details the physical contents, packaging type, weight, and dimensions of the shipment.
4.  **Certificado de Origen (Certificate of Origin):** 
    *   *Description:* Declares the country of manufacture. *Crucial in Chile* for applying tariff preferences under its extensive network of Tratados de Libre Comercio (TLC).
5.  **Certificado de Seguro (Insurance Certificate):** 
    *   *Description:* Proof of insurance coverage for the cargo during transit.

### 3.2 Suggested Documents for Chilean Customs (Agencia de Aduanas)
To fully support a Chilean operation, the system should also recognize:
6.  **Certificados Vistos Buenos (V°B°) / Resoluciones:**
    *   *Description:* Approvals required by Chilean governmental agencies for restricted goods (e.g., SAG for agriculture/wood packaging, Seremi de Salud for food/toys, ISP for medical/cosmetics, SEC for electrical items).
7.  **Mandato para Despacho / Poder:**
    *   *Description:* The legal authorization from the importer/exporter allowing the Agencia de Aduanas to clear the goods.
8.  **Declaración Jurada del Valor y sus Elementos:**
    *   *Description:* A required declaration under Chilean Customs (SNA) norms to justify the transaction value.
9.  **Other / Otros:** For unrecognized documents.

## 4. Workflows & Functional Requirements

### 4.1 Core Processing Engine
When documents are ingested, the system performs the following sequence:
1.  **OCR & Text Extraction:** Read text and layout.
2.  **Document Splitting:** Detect if a single PDF contains multiple distinct documents (e.g., pages 1-2 are the BL, page 3 is the Invoice) and split them.
3.  **Classification:** Identify the document types based on the list in Section 3.
4.  **Primary Data Extraction:** Extract the main Transport Document ID from the BL/AWB/CRT.
5.  **Consistency Check (Cross-Referencing):**
    *   The system scans the newly classified secondary documents (Invoice, Packing List, etc.).
    *   It looks for the Transport Document ID, matching container numbers, or matching Invoice/PO numbers across the set.
    *   *Objective:* Ensure all documents actually belong to the same shipment.
6.  **File Renaming:** Rename files using the normalized convention: `[Transport_ID]_[Document_Type].pdf` (e.g., `BL987654321_FacturaComercial.pdf`).
7.  **Archiving:** Compress into a ZIP file.
8.  **Report Generation:** Create a summary containing:
    *   *Processed:* Total files ingested.
    *   *Found:* List of identified documents.
    *   *Missing:* Expected standard documents not found.
    *   *Inconsistencies (Alerts):* Flag any document that failed the consistency check (e.g., "Warning: Factura Comercial does not reference BL987654321 - Possible mix-up").

### 4.2 Phase 1: Web Application Workflow (MVP)
*   **Trigger:** User logs into/navigates to the web app interface.
*   **UI/UX:** A drag-and-drop zone over the webpage interface for file uploads, alongside a standard file browser.
*   **Processing State:** While the Core Processing Engine works, the user sees a progress indicator (e.g., "Reading files...", "Splitting PDFs...", "Validating consistency...").
*   **Output / Delivery:** 
    *   The UI displays the Summary Report (Found, Missing, Inconsistencies) directly on the screen.
    *   A primary action button ("Download Organized ZIP") allows the user to download the processed files directly to their local machine.
* It should be deployed serverless in AWS infrastructure, for example, using AWS Amplify.

### 4.3 Phase 2: Email Workflow (Future Stage)
*   **Trigger:** Client forwards an email with attachments to a system address (e.g., `documentos@agencia.cl`).
*   **Validation:** System checks for attached PDFs. If none exist, it auto-replies with an error.
*   **Processing:** Attachments are routed through the Core Processing Engine.
*   **Output / Delivery:** 
    *   The system replies to the sender.
    *   The email body contains the Summary Report (Found, Missing, Inconsistencies).
    *   The email includes the organized ZIP file (or a secure, expiring download link if the file size exceeds email provider limits).

## 5. Non-Functional Requirements
*   **Accuracy:** OCR, Classification, and Consistency Checks should aim for >95% confidence on standardized templates.
*   **Performance:** Processing a standard 10-page batch on the web app should complete within 15-30 seconds.
*   **Security & Compliance:** Documents contain sensitive commercial data subject to Chilean data protection laws and customs secrecy. Files must be processed in memory where possible, encrypted at rest, and automatically purged from the server after the ZIP is downloaded.
*   **Language Support:** The OCR and AI classification must natively support Spanish (specifically Chilean customs terminology) and English.

## 6. Future Scope (Phase 3+)
*   Integration via API directly into the Customs Agency's ERP/Customs Software (e.g., Sigad, WebAduana) to auto-populate the *Declaración de Ingreso (DIN)*.
*   Advanced line-item extraction (HS codes, item weights, FOB/CIF values) to validate against customs regulations.
*   A "Human-in-the-Loop" dashboard where operators can manually correct consistency check failures or unclassified documents to retrain the model.