# Manual (no AI cost) check of rag.research() official-source routing: UK topic map, Wales nation, EU for ES, US limits
import asyncio
import rag

rag.is_enabled = lambda: False

CASES = [
    ("I was sacked after 3 years", "GB", "england"),
    ("my landlord in Cardiff wants me to move out and kept my deposit", "GB", None),
    ("my flight was cancelled by the airline", "ES", None),
    ("I was sacked after 3 years", "US", None),
]


async def main():
    for q, c, n in CASES:
        r = await rag.research(q, country=c, nation=n)
        print("=" * 100)
        print(q, c, n)
        print("KEYS", list(r.keys()))
        for cit in r.get("citations", []):
            print("  CIT", cit)
        blk = r.get("block") or r.get("context") or ""
        print("  SOURCE LIMITS in block:", "SOURCE LIMITS" in blk)
        print("  nation NOT confirmed in block:", "nation NOT confirmed" in blk)
        print("  directly applicable in Spain:", "directly applicable in Spain" in blk)
        print("  Acas in block:", "acas" in blk.lower(), "| legislation.gov.uk in block:", "legislation.gov.uk" in blk)
        print("  BLOCK HEAD:", blk[:1500].replace("\n", " | "))


asyncio.run(main())
