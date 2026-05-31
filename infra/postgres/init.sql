CREATE EXTENSION IF NOT EXISTS vector;

-- Trade history — diisi Quant Bot, dibaca Hermes
CREATE TABLE IF NOT EXISTS trades (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)   NOT NULL,
    side        VARCHAR(4)    NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity    DECIMAL(20,8) NOT NULL,
    entry_price DECIMAL(20,8) NOT NULL,
    exit_price  DECIMAL(20,8),
    pnl         DECIMAL(20,8),
    entry_time  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    exit_time   TIMESTAMPTZ,
    status      VARCHAR(20)   NOT NULL DEFAULT 'OPEN'
                              CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED'))
);

-- Log keputusan Hermes Agent
CREATE TABLE IF NOT EXISTS hermes_analyses (
    id           SERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger_type VARCHAR(10) NOT NULL CHECK (trigger_type IN ('CRON', 'ALERT')),
    decision     JSONB,
    reason       TEXT
);

-- Seed data untuk test tanpa Quant Bot aktif
INSERT INTO trades (symbol, side, quantity, entry_price, exit_price, pnl, exit_time, status)
VALUES
  ('AAPL', 'BUY', 10, 175.50, 178.20,  27.00, NOW() - INTERVAL '1 hour',  'CLOSED'),
  ('TSLA', 'BUY',  5, 240.00, 235.50, -22.50, NOW() - INTERVAL '2 hours', 'CLOSED'),
  ('NVDA', 'BUY',  3, 890.00, NULL,    NULL,  NULL,                        'OPEN');
