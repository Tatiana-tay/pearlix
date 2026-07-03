import type { AIResult, AIResultFinding, Attachment } from "../types/models";

export const mockAttachments: Attachment[] = [
  {
    File_ID: "FILE-001",
    File_Type: "Panoramic X-ray",
    File_Path: "mock-xray-panorama.svg",
    Upload_Date: "2026-02-05",
    Visit_ID: "VIS-002",
    Patient_ID: "PT-2218",
    Doctor_ID: "DOC-002",
  },
  {
    File_ID: "FILE-002",
    File_Type: "Bitewing X-ray",
    File_Path: "mock-bitewing.svg",
    Upload_Date: "2026-01-15",
    Visit_ID: "VIS-001",
    Patient_ID: "PT-1044",
    Doctor_ID: "DOC-001",
  },
];

export const mockAiResults: AIResult[] = [
  {
    Analysis_ID: "AI-001",
    File_ID: "FILE-001",
    Result_Summary: "Assistive review completed with several findings flagged for doctor confirmation.",
    Overall_Confidence: 0.86,
    Processed_Date: "2026-02-05",
    Model_Version: "DentalVision-R 0.8",
    Status: "Completed",
    Overlay_File_Path: "mock-overlay.svg",
  },
  {
    Analysis_ID: "AI-002",
    File_ID: "FILE-002",
    Result_Summary: "Image processing failed because the uploaded file contrast was too low.",
    Overall_Confidence: 0,
    Processed_Date: "2026-01-15",
    Model_Version: "DentalVision-R 0.8",
    Status: "Failed",
    Overlay_File_Path: "",
  },
];

export const mockAiFindings: AIResultFinding[] = [
  {
    Finding_ID: "FND-001",
    Analysis_ID: "AI-001",
    FDI_Tooth_ID: "16",
    Disease_Label: "Caries",
    Confidence_Score: 0.82,
  },
  {
    Finding_ID: "FND-002",
    Analysis_ID: "AI-001",
    FDI_Tooth_ID: "27",
    Disease_Label: "Deep Caries",
    Confidence_Score: 0.76,
  },
  {
    Finding_ID: "FND-003",
    Analysis_ID: "AI-001",
    FDI_Tooth_ID: "38",
    Disease_Label: "Impacted",
    Confidence_Score: 0.91,
  },
  {
    Finding_ID: "FND-004",
    Analysis_ID: "AI-001",
    FDI_Tooth_ID: "46",
    Disease_Label: "Periapical Lesion",
    Confidence_Score: 0.72,
  },
  {
    Finding_ID: "FND-005",
    Analysis_ID: "AI-001",
    FDI_Tooth_ID: "11",
    Disease_Label: "Caries",
    Confidence_Score: 0.68,
  },
];
