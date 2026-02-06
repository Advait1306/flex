"use client";

import { DocumentFeed } from "@/components/editor/DocumentFeed";
import { AuthGate } from "@/components/AuthGate";

export default function Home() {
  return (
    <AuthGate>
      <DocumentFeed />
    </AuthGate>
  );
}
