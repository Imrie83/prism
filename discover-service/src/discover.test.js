import { describe, it, expect } from "vitest";

// Extract and test the pure utility functions from discover.js
// Note: discoverBusinesses requires Playwright/browser, so we test the utilities

// Re-implement utility functions for testing (they're not exported)
function isBusinessWebsite(url) {
  if (!url) return false;
  if (!url.startsWith("http")) return false;
  const BLOCKED_DOMAINS = [
    "google.com", "goo.gl", "tripadvisor.", "booking.com", "expedia.",
    "airbnb.", "agoda.", "jalan.net", "ikyu.com", "instagram.com",
    "facebook.com", "twitter.com", "x.com", "youtube.com", "airhost.",
    "weniseko.", "holidayniseko.", "powderhounds.", "snowjapan.",
  ];
  return !BLOCKED_DOMAINS.some(d => url.includes(d));
}

describe("discover-service utilities", () => {
  describe("isBusinessWebsite", () => {
    it("should return false for null/undefined", () => {
      expect(isBusinessWebsite(null)).toBe(false);
      expect(isBusinessWebsite(undefined)).toBe(false);
    });

    it("should return false for empty string", () => {
      expect(isBusinessWebsite("")).toBe(false);
    });

    it("should return false for non-HTTP URLs", () => {
      expect(isBusinessWebsite("ftp://example.com")).toBe(false);
      expect(isBusinessWebsite("example.com")).toBe(false);
      expect(isBusinessWebsite("www.example.com")).toBe(false);
    });

    it("should return true for valid HTTP URLs", () => {
      expect(isBusinessWebsite("http://example.com")).toBe(true);
      expect(isBusinessWebsite("https://example.com")).toBe(true);
      expect(isBusinessWebsite("https://www.example.com")).toBe(true);
    });

    it("should return false for Google URLs", () => {
      expect(isBusinessWebsite("https://google.com")).toBe(false);
      expect(isBusinessWebsite("https://www.google.com/search")).toBe(false);
      expect(isBusinessWebsite("https://goo.gl/abc123")).toBe(false);
    });

    it("should return false for social media URLs", () => {
      expect(isBusinessWebsite("https://instagram.com/business")).toBe(false);
      expect(isBusinessWebsite("https://facebook.com/page")).toBe(false);
      expect(isBusinessWebsite("https://twitter.com/user")).toBe(false);
      expect(isBusinessWebsite("https://x.com/user")).toBe(false);
      expect(isBusinessWebsite("https://youtube.com/channel")).toBe(false);
    });

    it("should return false for travel platform URLs", () => {
      expect(isBusinessWebsite("https://tripadvisor.com/hotel")).toBe(false);
      expect(isBusinessWebsite("https://booking.com/hotel")).toBe(false);
      expect(isBusinessWebsite("https://airbnb.com/room")).toBe(false);
      expect(isBusinessWebsite("https://expedia.com/hotel")).toBe(false);
      expect(isBusinessWebsite("https://agoda.com/hotel")).toBe(false);
    });

    it("should return false for Japanese travel sites", () => {
      expect(isBusinessWebsite("https://jalan.net/hotel")).toBe(false);
      expect(isBusinessWebsite("https://ikyu.com/hotel")).toBe(false);
    });

    it("should return true for regular business websites", () => {
      expect(isBusinessWebsite("https://mybusiness.com")).toBe(true);
      expect(isBusinessWebsite("https://restaurant-tokyo.jp")).toBe(true);
      expect(isBusinessWebsite("http://local-cafe.com")).toBe(true);
    });

    it("should handle URLs with paths and query strings", () => {
      expect(isBusinessWebsite("https://example.com/path/to/page")).toBe(true);
      expect(isBusinessWebsite("https://example.com?query=value")).toBe(true);
      expect(isBusinessWebsite("https://google.com/maps/place")).toBe(false);
    });
  });

  describe("URL parsing", () => {
    it("should parse keywords correctly", () => {
      const keywords = "restaurant, hotel, cafe";
      const keywordList = keywords.split(",").map(k => k.trim()).filter(Boolean);
      expect(keywordList).toEqual(["restaurant", "hotel", "cafe"]);
    });

    it("should handle empty keywords", () => {
      const keywords = "";
      const keywordList = keywords.split(",").map(k => k.trim()).filter(Boolean);
      expect(keywordList).toEqual([]);
    });

    it("should handle keywords with extra spaces", () => {
      const keywords = "  restaurant ,  hotel  , cafe ";
      const keywordList = keywords.split(",").map(k => k.trim()).filter(Boolean);
      expect(keywordList).toEqual(["restaurant", "hotel", "cafe"]);
    });

    it("should construct search URL correctly", () => {
      const keyword = "restaurant";
      const location = "Tokyo";
      const query = [keyword, location].filter(Boolean).join(" ");
      const searchUrl = `https://www.google.com/maps/search/${encodeURIComponent(query)}`;

      expect(searchUrl).toBe("https://www.google.com/maps/search/restaurant%20Tokyo");
    });

    it("should handle keyword without location", () => {
      const keyword = "restaurant";
      const location = "";
      const query = [keyword, location].filter(Boolean).join(" ");
      const searchUrl = `https://www.google.com/maps/search/${encodeURIComponent(query)}`;

      expect(searchUrl).toBe("https://www.google.com/maps/search/restaurant");
    });
  });

  describe("deduplication key", () => {
    it("should create unique key from name and address", () => {
      const biz = { name: "Test Restaurant", address: "123 Main St" };
      const key = `${biz.name}||${biz.address}`;
      expect(key).toBe("Test Restaurant||123 Main St");
    });

    it("should handle same name different address", () => {
      const biz1 = { name: "Test Restaurant", address: "123 Main St" };
      const biz2 = { name: "Test Restaurant", address: "456 Oak Ave" };
      const key1 = `${biz1.name}||${biz1.address}`;
      const key2 = `${biz2.name}||${biz2.address}`;
      expect(key1).not.toBe(key2);
    });

    it("should handle different name same address", () => {
      const biz1 = { name: "Restaurant A", address: "123 Main St" };
      const biz2 = { name: "Restaurant B", address: "123 Main St" };
      const key1 = `${biz1.name}||${biz1.address}`;
      const key2 = `${biz2.name}||${biz2.address}`;
      expect(key1).not.toBe(key2);
    });
  });

  describe("email extraction regex", () => {
    it("should extract valid email from text", () => {
      const text = "Contact us at info@example.com for more info";
      const match = new RegExp(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/).exec(text);
      expect(match).not.toBeNull();
      expect(match[0]).toBe("info@example.com");
    });

    it("should extract complex email", () => {
      const text = "Email: john.doe+test@subdomain.example.co.jp";
      const match = new RegExp(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/).exec(text);
      expect(match).not.toBeNull();
      expect(match[0]).toBe("john.doe+test@subdomain.example.co.jp");
    });

    it("should return null for no email", () => {
      const text = "No email here just text";
      const match = new RegExp(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/).exec(text);
      expect(match).toBeNull();
    });

    it("should normalize email to lowercase", () => {
      const text = "Email: John@Example.COM";
      const match = new RegExp(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/).exec(text);
      expect(match[0].toLowerCase()).toBe("john@example.com");
    });
  });

  describe("Maps URL extraction", () => {
    it("should extract place ID from Maps URL", () => {
      const href = "https://www.google.com/maps/place/Some+Restaurant/@35.123,139.456,15z";
      const placeMatch = /\/maps\/place\/([^/@]+)/.exec(href);
      expect(placeMatch).not.toBeNull();
      expect(placeMatch[1]).toBe("Some+Restaurant");
    });

    it("should construct correct Maps URL", () => {
      const href = "https://www.google.com/maps/place/Test%20Business/@35.123,139.456";
      const placeMatch = /\/maps\/place\/([^/@]+)/.exec(href);
      const mapsUrl = placeMatch ? `https://www.google.com/maps/place/${placeMatch[1]}` : "";
      expect(mapsUrl).toBe("https://www.google.com/maps/place/Test%20Business");
    });
  });
});