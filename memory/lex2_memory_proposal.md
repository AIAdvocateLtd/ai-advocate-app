# Lex 2.0 memory proposal (draft for founder — nothing built)

Goal: Lex remembers the customer and their ongoing matters without mixing unrelated cases or compromising privacy.

## 1. Two kinds of memory
- Personal profile memory (opt-in): stable facts about the person — name to use, UK nation, language, household
  (e.g. "tenant", "has two children"), accessibility needs. Small, structured fields, not free text.
- Matter (case) memory: facts tied to ONE legal matter — parties, dates, amounts, documents, deadlines. Lives on the
  existing Case File; a chat linked to a case can use that case's memory only.
- Never: facts from matter A used in matter B. Cross-matter links are only SUGGESTED ("This may be the same landlord as
  your deposit case — is it?") and need a tap to confirm.

## 2. How facts are saved
- Lex proposes facts after a chat ("Save these 3 facts to your Deposit case?"); the customer approves, edits or rejects.
- Each fact stores: matter id, source conversation, date, who confirmed it, and "confirmed / unconfirmed".
- Lex treats unconfirmed facts as questions, never as evidence for legal conclusions.

## 3. Customer controls (GDPR Art. 15–17, 21)
- Settings → "What Lex remembers": view, edit, delete any fact; delete all; download a copy.
- Separate switches: profile memory on/off, use other matters for connections on/off (default off).
- Deleting a conversation or case deletes its derived memories.

## 4. Storage & security
- Encrypted at rest with the existing field encryption; per-user filtering on every query (as today).
- No memory text in logs or usage records (only counts), retention tied to account deletion.
- Special-category data (health, criminal, immigration status) flagged and only kept with explicit consent (Art. 9);
  update privacy notice + DPIA before launch.

## 5. Rollout
Stage A: matter memory on Case Files (customer-approved facts). Stage B: profile memory opt-in. Stage C: suggested
cross-matter links with confirmation. Flag LEX_CROSS_MEMORY_ENABLED + user.memory_consent.cross_chat already exist as the gate.
