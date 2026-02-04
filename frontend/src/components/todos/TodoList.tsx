"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/axios";

interface Todo {
  id: string;
  title: string;
  description?: string;
  parent_id?: string;
  status: "pending" | "in_progress" | "completed";
}

const getStatusColor = (status: Todo["status"]) => {
  switch (status) {
    case "completed":
      return "text-green-600 bg-green-50";
    case "in_progress":
      return "text-blue-600 bg-blue-50";
    default:
      return "text-gray-600 bg-gray-50";
  }
};

const getStatusLabel = (status: Todo["status"]) => {
  switch (status) {
    case "completed":
      return "Done";
    case "in_progress":
      return "In Progress";
    default:
      return "Pending";
  }
};

function TodoItem({
  todo,
  childrenByParent,
  expandedIds,
  toggleExpanded,
  depth = 0,
}: {
  todo: Todo;
  childrenByParent: Record<string, Todo[]>;
  expandedIds: Set<string>;
  toggleExpanded: (id: string) => void;
  depth?: number;
}) {
  const isExpanded = expandedIds.has(todo.id);
  const children = childrenByParent[todo.id] || [];
  const isTopLevel = depth === 0;

  return (
    <div
      className={
        isTopLevel
          ? "rounded-lg border border-border bg-card p-4 cursor-pointer hover:border-border/80 transition-colors"
          : "cursor-pointer py-1"
      }
      onClick={(e) => {
        e.stopPropagation();
        toggleExpanded(todo.id);
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <span
            className={
              isTopLevel
                ? `font-medium text-foreground ${isExpanded ? "" : "truncate"} block`
                : `text-sm text-muted-foreground ${isExpanded ? "" : "truncate"} block`
            }
          >
            {todo.title}
          </span>
          {todo.description && (
            <p
              className={`mt-1 ${isTopLevel ? "text-sm" : "text-xs"} text-muted-foreground ${isExpanded ? "whitespace-pre-wrap" : "line-clamp-2"}`}
            >
              {todo.description}
            </p>
          )}
        </div>
        <span
          className={`shrink-0 text-xs ${isTopLevel ? "px-2 py-1 rounded-full" : "px-1.5 py-0.5 rounded"} font-medium ${getStatusColor(todo.status)}`}
        >
          {getStatusLabel(todo.status)}
        </span>
      </div>

      {children.length > 0 && (
        <div className="mt-3 pl-4 border-l-2 border-border/50 space-y-2">
          {children.map((child) => (
            <TodoItem
              key={child.id}
              todo={child}
              childrenByParent={childrenByParent}
              expandedIds={expandedIds}
              toggleExpanded={toggleExpanded}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function TodoList() {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const { data, error, isLoading } = useSWR<{ todos: Todo[] }>(
    "/api/todos",
    fetcher,
    { refreshInterval: 2000 }
  );

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const todos = data?.todos || [];

  // Build a map of children by parent ID
  const childrenByParent = todos.reduce(
    (acc, t) => {
      const parentId = t.parent_id || "root";
      if (!acc[parentId]) acc[parentId] = [];
      acc[parentId].push(t);
      return acc;
    },
    {} as Record<string, Todo[]>
  );

  // Root todos are those without a parent
  const rootTodos = todos.filter((t) => !t.parent_id);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-muted-foreground text-sm">Loading todos...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-destructive text-sm">Failed to load todos</div>
      </div>
    );
  }

  if (todos.length === 0) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-muted-foreground text-sm">No todos yet</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {rootTodos.map((todo) => (
        <TodoItem
          key={todo.id}
          todo={todo}
          childrenByParent={childrenByParent}
          expandedIds={expandedIds}
          toggleExpanded={toggleExpanded}
        />
      ))}
    </div>
  );
}
