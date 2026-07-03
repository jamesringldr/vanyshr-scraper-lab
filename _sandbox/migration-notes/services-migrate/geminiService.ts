
import { GoogleGenAI, GenerateContentResponse } from "@google/genai";
import { EnrichedData } from '../types';

// Attempt to initialize the Gemini AI client
// Adhering to the strict instruction to use process.env.API_KEY directly in the constructor,
// but only if 'process' and 'process.env.API_KEY' are accessible.

let ai: GoogleGenAI | null = null;
let apiKeyIsAvailable = false;
let apiKeyInitializationError: string | null = null;

try {
  if (typeof process !== 'undefined' && process.env && typeof process.env.API_KEY === 'string' && process.env.API_KEY) {
    // This is the ONLY place process.env.API_KEY is used for instantiation as per guidelines
    ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    apiKeyIsAvailable = true;
  } else if (typeof process === 'undefined') {
    apiKeyInitializationError = "Gemini API key cannot be accessed: 'process' is not defined in this browser environment. Lead Enrichment will not function.";
  } else if (!process.env) {
    apiKeyInitializationError = "Gemini API key cannot be accessed: 'process.env' is not defined. Lead Enrichment will not function.";
  } else if (!process.env.API_KEY) {
    apiKeyInitializationError = "Gemini API key (process.env.API_KEY) is not set or is empty. Lead Enrichment will not function.";
  } else {
    apiKeyInitializationError = "Gemini API key (process.env.API_KEY) is not accessible for an unknown reason. Lead Enrichment will not function.";
  }
} catch (e) {
    apiKeyInitializationError = `Error during GoogleGenAI initialization: ${e instanceof Error ? e.message : String(e)}`;
    console.error(apiKeyInitializationError);
}


if (apiKeyInitializationError && !apiKeyIsAvailable) {
    console.error(apiKeyInitializationError);
}


const modelName = "gemini-2.5-flash-preview-04-17"; // Corrected model name as per guidelines

export const enrichCompanyInfo = async (companyName: string): Promise<EnrichedData> => {
  if (!ai || !apiKeyIsAvailable) {
     return Promise.reject(new Error(apiKeyInitializationError || "Gemini API client is not initialized, likely due to a missing or inaccessible API key."));
  }
  const prompt = `
    Provide a brief summary of the company "${companyName}". 
    Include its primary industry, official website, general location (e.g., city, country), and approximate employee count if publicly known.
    Respond strictly in JSON format with the following structure: 
    {
      "summary": "string", 
      "industry": "string | null", 
      "website": "string | null",
      "location": "string | null",
      "employeeCount": "string | null"
    }
    If a field is not applicable or unknown, provide null or an empty string for its value.
    For example:
    {
      "summary": "A multinational technology company specializing in internet-related services and products.",
      "industry": "Technology",
      "website": "https://www.example.com",
      "location": "Mountain View, CA, USA",
      "employeeCount": "100,000+"
    }
  `;

  try {
    // Using the correct generateContent structure
    const response: GenerateContentResponse = await ai.models.generateContent({
        model: modelName, // Use the defined model variable
        contents: [{ role: "user", parts: [{ text: prompt }] }], // Correct contents structure
        config: {
            responseMimeType: "application/json",
        }
    });

    let jsonStr = response.text?.trim() || ''; // Access text directly as per guidelines
    
    const fenceRegex = /^```(\w*)?\s*\n?(.*?)\n?\s*```$/s;
    const match = jsonStr.match(fenceRegex);
    if (match && match[2]) {
      jsonStr = match[2].trim();
    }

    const parsedData = JSON.parse(jsonStr) as EnrichedData;
    return parsedData;

  } catch (error) {
    console.error("Error enriching company info:", error);
    let errorMessage = "Failed to enrich company information.";
    if (error instanceof Error) {
        errorMessage = error.message;
    }
    throw new Error(`Gemini API Error: ${errorMessage}`);
  }
};
