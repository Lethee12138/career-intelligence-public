# Capability → Role Family → Market Title Taxonomy

This is a stable vocabulary bridge for `/position`, `/discover` and search handoffs.
It is a hypothesis-generation aid, not candidate evidence, market validation or an
application recommendation. A supplied current JD and authoritative market source
override this vocabulary. Title variants must still be checked against actual duties.

## Mapping contract

Each mapping keeps four layers distinct:

| Field | Meaning |
| --- | --- |
| `capability` | A grounded capability root or bounded capability hypothesis. |
| `role_family` | The responsibility family to investigate. |
| `market_title_variants` | Search vocabulary for different employers and markets; variants are not equivalent jobs. |
| `negative_title_traps` | Titles or duty patterns that require duty-level verification; they are not automatic exclusions. |

AI involvement is an attribute of a role hypothesis, not a role-family admission
gate. The same capability can produce an `AI-CORE`, `AI-ENABLED` or `NONE`
hypothesis when the actual work supports it.

## Core mappings

| Capability | Role family | Market title variants | Negative title traps |
| --- | --- | --- | --- |
| Product framing, prioritisation, user/problem definition, cross-functional delivery | `PRODUCT` | Product Manager; Product Owner; Digital Product Manager; Product Specialist; Associate Product Manager | Product Consultant with quota or client acquisition; Product Manager with engineering ownership; Product Specialist that is primarily sales or account management |
| Human-AI workflow framing, AI-assisted product decisions, bounded intelligent workflow design | `AI_PRODUCT_HUMAN_AI_WORKFLOW` | AI Product Manager; Human-AI Workflow Product Manager; Intelligent Product Manager; AI Experience Product Manager; Agent Product Manager | Agent/RAG/LLM title used for software engineering; presales AI consultant; deployment/architecture ownership; technical depth not supported by evidence |
| User behaviour research, interview synthesis, usability or product insight | `USER_PRODUCT_RESEARCH` | User Researcher; Product Researcher; UX Researcher; Researcher, Product Insights; Customer Insights Researcher | Market Research with sales/recruitment quota; research operations without research ownership; research title requiring domain or methods not evidenced |
| Workflow coordination, product operating cadence, cross-functional systems and process improvement | `PRODUCT_OPERATIONS` | Product Operations Manager; Product Ops Specialist; Product Enablement Manager; Product Workflow Operations; Product Program Coordinator | Growth/revenue operations; Sales Operations; customer acquisition; quota ownership; program title that is mainly administrative coordination |
| Cross-team workflow change, business improvement, digital operating model or adoption | `DIGITAL_TRANSFORMATION` | Digital Transformation Analyst; Digital Transformation Consultant; Business Transformation Manager; Workflow Transformation Lead; Digital Adoption Manager | Presales-heavy consulting; implementation delivery requiring unsupported technical ownership; ERP or engineering delivery hidden behind transformation wording |
| Ambiguous problem framing, new-venture exploration, strategic experimentation and innovation portfolio work | `INNOVATION` | Innovation Strategist; Innovation Program Manager; Business Innovation Analyst; Innovation Associate; Venture Innovation Manager | Pitch-only or event production; strategy consulting with acquisition/negotiation-heavy duties; innovation title without owned problem, experiment or delivery scope |
| Experience framing, service journey design, customer experience and interaction/system improvement | `EXPERIENCE_SERVICE_DESIGN` | Service Designer; Experience Designer; Customer Experience Strategist; Customer Journey Designer; Product Experience Designer; CX Researcher | High-craft visual/UI production; industrial or spatial design; front-end implementation; CX role that is primarily call-centre operations or sales |

## Discovery use

For each hypothesis, preserve the originating capability evidence and add the
taxonomy `role_family` plus a bounded subset of title variants. Record omitted
families and why they were not grounded. Keep `AI-CORE`, `AI-ENABLED` and `NONE`
lanes visible during coverage review; do not replace broad discovery with AI title
matching. Negative title traps trigger duty-level verification and may route to a
qualification or preference review, but do not erase the family.

The taxonomy does not establish hiring demand, eligibility, sponsorship, salary,
candidate fit or current availability.
