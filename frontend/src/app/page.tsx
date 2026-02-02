"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [message, setMessage] = useState<string>("Loading...");

  useEffect(() => {
    fetch("http://localhost:8000/")
      .then((res) => res.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage("Backend not running"));
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <main className="flex flex-col items-center gap-8 p-8">
        <h1 className="text-4xl font-bold text-zinc-900 dark:text-white">
          Next.js + FastAPI
        </h1>
        <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-lg text-zinc-600 dark:text-zinc-400">
            Backend says:{" "}
            <span className="font-medium text-zinc-900 dark:text-white">
              {message}
            </span>
          </p>
        </div>
        <p className="text-sm text-zinc-500">
          Edit <code className="font-mono">src/app/page.tsx</code> to get started
        </p>
      </main>
    </div>
  );
}
