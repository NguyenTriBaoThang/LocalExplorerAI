# Local Explorer AI — Demo Presentation Script

This document guides a presenter or judge through a **5–7 minute** live demonstration of **Local Explorer AI**.

> This is the original demo narrative translated into English. Some routes, visuals, timings, and feature claims may have changed or may be illustrative; verify them against the current build before presenting, and label simulated data or unavailable integrations accurately.

---

## ⏱️ Demo Timing Overview

| Duration | Segment | Main Goal |
| :---: | :--- | :--- |
| **0:00 - 0:45** | Opening and problem | Introduce the paradox: “On the map ≠ available to experience when you arrive.” |
| **0:45 - 2:00** | Explore the 3D WebGL Saigon hero | Demonstrate the interactive 3D canvas, mouse rotation, and radar pins. |
| **2:00 - 3:30** | Explore experiences and multidimensional filters | Filter by intent (food, handicrafts) and try the 3D tilt cards. |
| **3:30 - 4:45** | Three-step smart itinerary planning | Enter trip details and inspect the 3D Live Day Preview card. |
| **4:45 - 5:45** | 3D journey timeline and AI explanation | Review four KPI cards, the laser timeline, and feasibility transparency. |
| **5:45 - 6:30** | Partner portal and conclusion | Introduce the slot-management workspace and summarize the value for Ho Chi Minh City. |

---

## 🚀 Detailed Step-by-Step Script

### Step 1: Opening and Problem Statement (0:00 - 0:45)
- **Action:** Open the home page at `http://localhost:5173`.
- **Presenter script:**
  > *“Judges, when traveling in Ho Chi Minh City, most of us use Google Maps. But a venue being open does not mean its experiences are currently running. Visitors may arrive after a workshop has ended or find that it is fully booked. Local Explorer AI was created to solve this problem: **discover the right experience at the right time**.”*

### Step 2: Demonstrate the 3D WebGL Space (0:45 - 2:00)
- **Action:** Move the cursor over the 3D Saigon city view, hover over POI pins, and click the Neon Night/Day mode switch.
- **Presenter script:**
  > *“On screen is a 3D digital twin of Saigon rendered with Three.js. The high-rises glow, the Saigon River reflects light, and 3D pins emit radar-like pulses. As you move the mouse, the camera smoothly shifts with a parallax effect, giving visitors an intuitive, vivid sense of the city.”*

### Step 3: Explore Experiences and Multidimensional Filters (2:00 - 3:30)
- **Action:** Click *Explore experiences* (`/explore`). Select the *Handicrafts* tag and adjust the budget and group size.
- **Presenter script:**
  > *“On the Explore page, activities such as Dó paper making, sock coffee tasting, and pottery are displayed in 3D tilt cards with a reflective light effect. The CartoDB map on the right automatically moves to the selected coordinates and stays synchronized with the list.”*

### Step 4: Plan an Itinerary and Preview It in 3D (3:30 - 4:45)
- **Action:** Navigate to `/planner`. Enter tomorrow, 09:00–16:00, a group of two, and a budget of VND 1,200,000. Select *Food* and *Handicrafts*.
- **Presenter script:**
  > *“This is the three-step smart itinerary wizard. Please look at the 3D Preview card on the right: when I change the time or add a preference, the card recalculates total hours, average cost per person, and the best travel mode in real time.”*

### Step 5: Journey Timeline and AI Explanation (4:45 - 5:45)
- **Action:** Click *Create itinerary now*. The `/itinerary/:id` page appears with four glowing 3D KPI cards.
- **Presenter script:**
  > *“In under 50 ms, the heuristic algorithm has produced a complete journey. A 3D timeline connects stops with a laser-like line and clearly shows estimated travel time between districts. Below it, a transparent explanation card with reason codes shows why the AI recommended each activity and flags activities that need confirmation.”*

### Step 6: Partner Portal and Conclusion (5:45 - 6:30)
- **Action:** Navigate to `/provider` and briefly show the slot-management dashboard.
- **Presenter script:**
  > *“Local Explorer AI serves not only travelers but also artisans and traditional craft workshops through the Partner Portal. With an open architecture, transparent data, and 3D visuals, the project aims to support smart tourism and preserve Ho Chi Minh City's cultural heritage. Thank you, judges!”*
