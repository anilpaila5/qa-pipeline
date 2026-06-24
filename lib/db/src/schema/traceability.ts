import { pgTable, serial, text, integer, timestamp } from "drizzle-orm/pg-core";

export const traceabilityEntriesTable = pgTable("traceability_entries", {
  id: serial("id").primaryKey(),
  jiraKey: text("jira_key").notNull(),
  tcName: text("tc_name").notNull(),
  bsTcId: text("bs_tc_id").notNull(),
  folderId: integer("folder_id"),
  automationMethod: text("automation_method"),
  automationFile: text("automation_file"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export type TraceabilityEntry = typeof traceabilityEntriesTable.$inferSelect;
export type InsertTraceabilityEntry = typeof traceabilityEntriesTable.$inferInsert;
