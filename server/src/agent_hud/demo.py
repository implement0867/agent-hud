"""Sample board for UI development (`agent-hud --mode serve --demo`)."""

from agent_hud.board import Board
from agent_hud.ops import ClearOp, LinkOp, Op, OpKind, PutOp


def seed(board: Board) -> None:
    ops: list[Op] = [
        ClearOp(op=OpKind.CLEAR),
        PutOp(
            op=OpKind.PUT,
            id="plan",
            md="""## Migration plan
1. Freeze writes to the legacy `orders` table
2. Backfill the new schema in batches
3. Dual-write from the API for one release
4. Compare row counts and checksums nightly
5. Switch reads to the new schema behind a flag
6. Drop the legacy table after two clean weeks
   - keep a cold backup in S3""",
        ),
        PutOp(
            op=OpKind.PUT,
            id="opts",
            md="""## Queue options
| Option | Latency | Ops cost | Pick {check} | Effort {low,med,high} | Notes {text} |
|---|---|---|---|---|---|
| Redis Streams | ~1 ms | low | | med | |
| SQS | ~20 ms | none | | low | |
| Kafka | ~5 ms | high | | high | |""",
        ),
        PutOp(
            op=OpKind.PUT,
            id="risk",
            md="""## Open risk
The backfill holds a **share lock** per batch. With 40M rows and 10k-row batches
that is ~4,000 short locks. We expect p99 write latency to rise by 5-10 ms during
the window.""",
        ),
        PutOp(
            op=OpKind.PUT,
            id="env",
            md="""| Env | Region | Replicas |
|---|---|---|
| staging | eu-west-1 | 1 |
| prod | eu-west-1 | 3 |""",
            title="Environments",
        ),
        LinkOp(op=OpKind.LINK, src="plan.4", dst="plan.3", text="needs"),
    ]
    board.apply(ops)
