import { describe, it, expect, beforeEach, vi } from "vitest";
import { useEmailStore } from "./emailStore.js";
import { api } from "../lib/api.js";

// Mock the api module
vi.mock("../lib/api.js", () => ({
  api: {
    generateEmail: vi.fn(),
  },
}));

describe("emailStore", () => {
  beforeEach(() => {
    useEmailStore.setState({
      emails: {},
      drawerUrl: null,
    });
    vi.clearAllMocks();
  });

  describe("drawer management", () => {
    it("should open drawer for a URL", () => {
      useEmailStore.getState().openDrawerFor("https://example.com");
      expect(useEmailStore.getState().drawerUrl).toBe("https://example.com");
    });

    it("should close drawer", () => {
      useEmailStore.getState().openDrawerFor("https://example.com");
      useEmailStore.getState().closeDrawer();
      expect(useEmailStore.getState().drawerUrl).toBeNull();
    });

    it("should get email for a URL", () => {
      useEmailStore.setState({
        emails: {
          "https://example.com": { status: "ready", subject: "Test" },
        },
      });

      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.status).toBe("ready");
      expect(email.subject).toBe("Test");
    });

    it("should return null for unknown URL", () => {
      const email = useEmailStore.getState().getEmail("https://unknown.com");
      expect(email).toBeNull();
    });
  });

  describe("email field setters", () => {
    beforeEach(() => {
      useEmailStore.setState({
        emails: {
          "https://example.com": { status: "idle" },
        },
      });
    });

    it("should set recipient email", () => {
      useEmailStore.getState().setRecipient("https://example.com", "test@example.com");
      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.recipientEmail).toBe("test@example.com");
    });

    it("should set subject", () => {
      useEmailStore.getState().setSubject("https://example.com", "Hello");
      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.subject).toBe("Hello");
    });

    it("should set HTML content", () => {
      useEmailStore.getState().setHtmlContent("https://example.com", "<p>Test</p>");
      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.htmlContent).toBe("<p>Test</p>");
    });

    it("should set checked issues", () => {
      useEmailStore.getState().setCheckedIssues("https://example.com", [0, 2, 3]);
      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.checkedIssues).toEqual([0, 2, 3]);
    });
  });

  describe("generate email", () => {
    it("should not generate if already generating or queued", async () => {
      useEmailStore.setState({
        emails: {
          "https://example.com": { status: "generating" },
        },
      });

      await useEmailStore.getState().generate("https://example.com", {}, {});
      expect(api.generateEmail).not.toHaveBeenCalled();
    });

    it("should set status to queued then generating", async () => {
      api.generateEmail.mockResolvedValue({
        subject: "Generated Subject",
        html: "<p>Generated content</p>",
        _tokens: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
      });

      const generatePromise = useEmailStore.getState().generate(
        "https://example.com",
        { issues: [] },
        { aiProvider: "ollama" }
      );

      // Check queued status immediately
      expect(useEmailStore.getState().emails["https://example.com"].status).toBe("queued");

      await generatePromise;

      // After completion
      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.status).toBe("ready");
      expect(email.subject).toBe("Generated Subject");
      expect(email.htmlContent).toBe("<p>Generated content</p>");
    });

    it("should accumulate tokens across regenerations", async () => {
      api.generateEmail
        .mockResolvedValueOnce({
          subject: "Subject 1",
          html: "<p>Content 1</p>",
          _tokens: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
        })
        .mockResolvedValueOnce({
          subject: "Subject 2",
          html: "<p>Content 2</p>",
          _tokens: { prompt_tokens: 120, completion_tokens: 60, total_tokens: 180 },
        });

      // First generation
      await useEmailStore.getState().generate("https://example.com", {}, {});

      let email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.tokensTotal.generationCount).toBe(1);
      expect(email.tokensTotal.total_tokens).toBe(150);

      // Second generation (regenerate)
      await useEmailStore.getState().generate("https://example.com", {}, {});

      email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.tokensTotal.generationCount).toBe(2);
      expect(email.tokensTotal.total_tokens).toBe(330); // 150 + 180
      expect(email.tokensLast.total_tokens).toBe(180); // last generation only
    });

    it("should handle generation errors", async () => {
      api.generateEmail.mockRejectedValue(new Error("API error"));

      await useEmailStore.getState().generate("https://example.com", {}, {});

      const email = useEmailStore.getState().getEmail("https://example.com");
      expect(email.status).toBe("error");
      expect(email.error).toBe("API error");
    });
  });

  describe("reset", () => {
    it("should reset a single URL", () => {
      useEmailStore.setState({
        emails: {
          "https://a.com": { status: "ready" },
          "https://b.com": { status: "ready" },
        },
      });

      useEmailStore.getState().resetUrl("https://a.com");

      expect(useEmailStore.getState().emails["https://a.com"]).toBeUndefined();
      expect(useEmailStore.getState().emails["https://b.com"]).toBeDefined();
    });

    it("should reset all emails", () => {
      useEmailStore.setState({
        emails: {
          "https://a.com": { status: "ready" },
          "https://b.com": { status: "ready" },
        },
        drawerUrl: "https://a.com",
      });

      useEmailStore.getState().resetAll();

      const state = useEmailStore.getState();
      expect(state.emails).toEqual({});
      expect(state.drawerUrl).toBeNull();
    });
  });
});