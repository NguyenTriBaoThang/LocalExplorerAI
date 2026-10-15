# Local Explorer AI — Project Submission (Competition Submission)

> This translated submission preserves the original project narrative. Its technical claims are proposal-era descriptions, not current deployment evidence; verify each claim against the current code and staging results before external use.

## 1. Project Information

- **Project name:** Local Explorer AI
- **Full title:** A Smart Urban Experience Discovery and Time-Slot-Aware Itinerary Planning Platform for Ho Chi Minh City, using 3D WebGL Graphics and a Heuristic Travel Optimization Algorithm.
- **Competition fields:** Smart City, AI Innovation, Digital Tourism, and Local Cultural Preservation.
- **Author / Team Lead:** Nguyễn Trí Bảo Thắng
- **Completion year:** 2026

---

## 2. Problem Statement

1. **The paradox of current digital travel maps:**
   - Popular mapping platforms generally provide static spatial information (longitude/latitude) and general business opening hours.
   - A venue being open from 8:00 to 21:00 does not mean that a pottery workshop, Southern Vietnamese cooking class, or sunset boat trip runs throughout that period. Travelers can arrive only to find that an activity's session has ended or is full.
2. **Overloaded information and LLM chatbot hallucinations:**
   - Using ChatGPT to plan an itinerary can produce infeasible plans: invented addresses, inaccurate urban travel-time estimates, and incorrect prices.
3. **Connecting the night-time economy with sustainable cultural tourism:**
   - Traditional craft businesses, heritage sock-coffee shops, and local cultural spaces in Ho Chi Minh City can have difficulty reaching the right travelers during their available hours.

---

## 3. Solution and Technical Innovation

**Local Explorer AI** addresses the problem through a system built around four pillars:

1. **Three-level data model (POI → Experience → Slot):** Clearly separates a place, a specific activity, and an actual time slot with capacity.
2. **Mathematical heuristic planner:** Creates deterministic itineraries and aims to optimize four factors together: preferences, budget, opening hours, and a Haversine travel-distance matrix.
3. **3D WebGL interface (Three.js):** Enriches the visual experience with a Saigon digital twin, parallax camera motion, and interactive 3D tilt cards.
4. **Data transparency:** Clearly marks feasibility (`feasible` vs `tentative`) and explains recommendations with reason codes.
