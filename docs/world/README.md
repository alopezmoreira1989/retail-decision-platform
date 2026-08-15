# Phase 1 — Retail World / Ground Truth: Design Documents

This folder holds the incremental, **document-by-document** design of Phase 1 (see [../SIMULATION.md](../SIMULATION.md) and [../../CLAUDE.md](../../CLAUDE.md) for why Phase 1 exists and what it may/may not contain).

## Why this exists as a separate, staged process

The user wants to review the simulated business model at every stage, drawing on professional experience in enterprise retail analytics. So Phase 1 is *not* designed as one large domain model — it's designed one document at a time:

1. Claude Code proposes a design for one domain, explaining assumptions explicitly rather than presenting them as settled fact.
2. The user reviews it for realism, internal consistency, and business plausibility.
3. Once approved, the design is considered stable enough to implement against (later, in a separate implementation task).
4. Only then does the next document get drafted.

Later documents may depend on earlier ones — the order below is a starting point, not a fixed sequence, and can be reordered if dependencies suggest otherwise.

## Documents

| # | Document | Status |
|---|---|---|
| 1 | [Company & Business Context](01-company-and-business-context.md) | **Approved** |
| 2 | [Product Universe](02-product-universe.md) | **Approved** |
| 3 | [Retailer Universe](03-retailer-universe.md) | **Approved** |
| 4 | [Store Universe](04-store-universe.md) | **Approved** |
| 5 | [Assortment](05-assortment.md) | **Approved** |
| 6 | [Demand](06-demand.md) | **Approved** |
| 7 | [Sales / POS Reality](07-sales-pos-reality.md) | **Approved** |
| 8 | Inventory | Not started |
| 9 | Orders / Replenishment | Not started |
| 10 | Promotions & Events | Not started |
| 11 | Commercial Activity | Not started |

These are planning documents, not schemas or code. None of this folder's content should be treated as implemented or final until its status says otherwise.
