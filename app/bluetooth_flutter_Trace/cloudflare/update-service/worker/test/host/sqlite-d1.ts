// Host-only adapter: SQLite executes all SQL, constraints, triggers and rollback.
// It is not evidence that the Cloudflare runtime/bindings executed successfully.
import { DatabaseSync, type SQLInputValue } from "node:sqlite";

export class SqliteD1 {
  readonly sqlite = new DatabaseSync(":memory:");
  constructor() { this.sqlite.exec("PRAGMA foreign_keys=ON"); }
  prepare(sql: string) { return new Statement(this, sql); }
  async batch<T>(statements: Statement[]): Promise<D1Result<T>[]> {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const result = statements.map((s) => s.execute<T>());
      this.sqlite.exec("COMMIT");
      return result;
    } catch (error) { this.sqlite.exec("ROLLBACK"); throw error; }
  }
  async exec(sql: string) {
    this.sqlite.exec(sql);
    return { count: 1, duration: 0 };
  }
  migrate(sql: string) {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try { this.sqlite.exec(sql); this.sqlite.exec("COMMIT"); }
    catch (error) { this.sqlite.exec("ROLLBACK"); throw error; }
  }
}

class Statement {
  constructor(readonly db: SqliteD1, readonly sql: string, readonly values: SQLInputValue[] = []) {}
  bind(...values: SQLInputValue[]) { return new Statement(this.db, this.sql, values); }
  execute<T>(): D1Result<T> {
    const statement = this.db.sqlite.prepare(this.sql);
    const reader = statement.columns().length > 0;
    const results = reader ? statement.all(...this.values) : [];
    const change = reader ? this.db.sqlite.prepare("SELECT changes() AS n").get()!.n : statement.run(...this.values).changes;
    return { results: results as T[], success: true, meta: { changes: Number(change), duration: 0,
      last_row_id: 0, changed_db: true, size_after: 0, rows_read: results.length, rows_written: Number(change) } };
  }
  async all<T>() { return this.execute<T>(); }
  async run<T>() { return this.execute<T>(); }
  async first<T>(column?: string): Promise<T | null> {
    const row = this.execute<Record<string, unknown>>().results[0];
    return row ? (column ? row[column] : row) as T : null;
  }
  async raw<T>() { return this.execute<Record<string, unknown>>().results.map(Object.values) as T[]; }
}
