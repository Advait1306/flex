"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/axios";

interface Fact {
  id: string;
  fact: string;
  category: "preference" | "personal" | "work" | "context" | "other";
  tags?: string[];
  source_trigger?: string;
  created_at?: string;
}

const getCategoryColor = (category: Fact["category"]) => {
  switch (category) {
    case "preference":
      return "text-purple-600 bg-purple-50";
    case "personal":
      return "text-pink-600 bg-pink-50";
    case "work":
      return "text-blue-600 bg-blue-50";
    case "context":
      return "text-amber-600 bg-amber-50";
    default:
      return "text-gray-600 bg-gray-50";
  }
};

const getCategoryLabel = (category: Fact["category"]) => {
  switch (category) {
    case "preference":
      return "Preference";
    case "personal":
      return "Personal";
    case "work":
      return "Work";
    case "context":
      return "Context";
    default:
      return "Other";
  }
};

function FactItem({ fact }: { fact: Fact }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className="rounded-lg border border-border bg-card p-4 cursor-pointer hover:border-border/80 transition-colors"
      onClick={() => setIsExpanded(!isExpanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p
            className={`text-sm text-foreground ${isExpanded ? "whitespace-pre-wrap" : "line-clamp-2"}`}
          >
            {fact.fact}
          </p>
          {fact.tags && fact.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {fact.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
        <span
          className={`shrink-0 text-xs px-2 py-1 rounded-full font-medium ${getCategoryColor(fact.category)}`}
        >
          {getCategoryLabel(fact.category)}
        </span>
      </div>
    </div>
  );
}

export function FactsList() {
  const { data, error, isLoading } = useSWR<{ facts: Fact[] }>(
    "/api/facts",
    fetcher,
    { refreshInterval: 500 }
  );

  const facts = data?.facts || [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-muted-foreground text-sm">Loading facts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-destructive text-sm">Failed to load facts</div>
      </div>
    );
  }

  if (facts.length === 0) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-muted-foreground text-sm">No facts yet</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {facts.map((fact) => (
        <FactItem key={fact.id} fact={fact} />
      ))}
    </div>
  );
}
