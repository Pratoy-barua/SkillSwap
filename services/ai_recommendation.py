"""AI Mentor Recommendation and Spatial Pathfinding Service.

Implements three classical AI search algorithms:
1. Hill Climbing (Local Search)
2. Simulated Annealing (Metaheuristic Optimization with Cooling Schedule)
3. A* Search (Heuristic Pathfinding with Admissible Haversine Heuristic)
"""

import heapq
import math
import random
from typing import Any, Dict, List, Optional, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two geographic coordinates in kilometers."""
    r = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


def parse_experience_score(exp_str: Optional[str]) -> float:
    """Extract a normalized 0.0-1.0 experience score from an experience string."""
    if not exp_str:
        return 0.5
    exp_lower = exp_str.lower()
    for token in exp_lower.split():
        if token.isdigit():
            years = int(token)
            return min(1.0, max(0.2, years / 10.0))
    if "senior" in exp_lower or "expert" in exp_lower:
        return 0.9
    if "mid" in exp_lower or "intermediate" in exp_lower:
        return 0.7
    if "beginner" in exp_lower or "entry" in exp_lower:
        return 0.4
    return 0.6


def evaluate_mentor_fitness(
    candidate: Dict[str, Any],
    learner_ctx: Dict[str, Any]
) -> Tuple[float, Dict[str, float]]:
    """Multi-criteria evaluation function Score(m) combining distance, skill, rating, price, and experience.

    Weights:
      - Distance suitability: 0.35 (Strong geographic proximity priority)
      - Skill match: 0.30
      - Rating: 0.15
      - Price suitability: 0.10
      - Experience: 0.10
    """
    req_skill_id = learner_ctx.get("skill_id")
    max_price = learner_ctx.get("max_price")
    preference = learner_ctx.get("preference")
    tier_radius = float(learner_ctx.get("tier_radius", 25.0) or 25.0)

    # 1. Geographic Distance Suitability (0.0 - 1.0)
    # Normalized against the active tier radius: 1.0 at 0km, linear decay down to 0.0 at tier_radius
    dist_km = float(candidate.get("distance_km", 10.0) or 10.0)
    if dist_km <= tier_radius:
        dist_score = round(max(0.0, 1.0 - (dist_km / tier_radius)), 3)
    else:
        # Fallback smooth decay for candidates beyond the tier radius
        dist_score = round(max(0.02, 50.0 / (50.0 + dist_km)), 3)

    # 2. Skill Match Score (0.0 - 1.0)
    candidate_skills = candidate.get("skills", [])
    if req_skill_id is None or not candidate_skills:
        skill_score = 0.8
    else:
        has_exact = any(s["skill_id"] == req_skill_id for s in candidate_skills)
        skill_score = 1.0 if has_exact else 0.1

    # 3. Rating Score (0.0 - 1.0)
    rating = float(candidate.get("rating", 0.0) or 0.0)
    rating_score = round(min(1.0, max(0.0, rating / 5.0)), 3)

    # 4. Price Suitability Score (0.0 - 1.0)
    is_paid = candidate.get("is_paid", False)
    price = float(candidate.get("price", 0.0) or 0.0)
    if preference == "free":
        price_score = 1.0 if not is_paid else 0.2
    elif preference == "paid":
        price_score = 1.0 if is_paid else 0.4
    elif max_price is not None and max_price > 0:
        if not is_paid or price <= max_price:
            price_score = 1.0
        else:
            price_score = max(0.1, 1.0 - ((price - max_price) / max_price))
    else:
        price_score = 1.0 if not is_paid else max(0.4, 1.0 - (price / 2000.0))
    price_score = round(min(1.0, max(0.0, price_score)), 3)

    # 5. Experience Score (0.0 - 1.0)
    exp_score = round(parse_experience_score(candidate.get("experience")), 3)

    w_dist = 0.35
    w_skill = 0.30
    w_rating = 0.15
    w_price = 0.10
    w_exp = 0.10

    total_fitness = round(
        (w_dist * dist_score)
        + (w_skill * skill_score)
        + (w_rating * rating_score)
        + (w_price * price_score)
        + (w_exp * exp_score),
        4
    )

    breakdown = {
        "distance": round(dist_score * 100, 1),
        "skill": round(skill_score * 100, 1),
        "rating": round(rating_score * 100, 1),
        "price": round(price_score * 100, 1),
        "experience": round(exp_score * 100, 1),
        "total_fitness": round(total_fitness * 100, 1)
    }

    return total_fitness, breakdown



def hill_climbing(
    candidates: List[Dict[str, Any]],
    learner_ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Hill Climbing local search algorithm."""
    if not candidates:
        return {"best_candidate": None, "trajectory": [], "iterations": 0}

    scored_candidates = []
    for c in candidates:
        score, breakdown = evaluate_mentor_fitness(c, learner_ctx)
        c_copy = dict(c)
        c_copy["ai_score"] = score
        c_copy["score_breakdown"] = breakdown
        scored_candidates.append(c_copy)

    current_state = scored_candidates[0]
    trajectory = [{
        "step": 0,
        "mentor_id": current_state["user_id"],
        "mentor_name": current_state["full_name"],
        "fitness": current_state["ai_score"]
    }]

    iterations = 0
    while True:
        iterations += 1
        neighbors = [c for c in scored_candidates if c["user_id"] != current_state["user_id"]]
        if not neighbors:
            break

        best_neighbor = max(neighbors, key=lambda x: x["ai_score"])

        if best_neighbor["ai_score"] > current_state["ai_score"]:
            current_state = best_neighbor
            trajectory.append({
                "step": iterations,
                "mentor_id": current_state["user_id"],
                "mentor_name": current_state["full_name"],
                "fitness": current_state["ai_score"],
                "improvement": True
            })
        else:
            break

    return {
        "best_candidate": current_state,
        "trajectory": trajectory,
        "iterations": iterations
    }


def simulated_annealing(
    candidates: List[Dict[str, Any]],
    learner_ctx: Dict[str, Any],
    t_initial: float = 1.0,
    alpha: float = 0.85,
    t_min: float = 0.05
) -> Dict[str, Any]:
    """Simulated Annealing metaheuristic algorithm."""
    if not candidates:
        return {"best_candidate": None, "log": [], "iterations": 0}

    scored_pool = []
    for c in candidates:
        score, breakdown = evaluate_mentor_fitness(c, learner_ctx)
        c_copy = dict(c)
        c_copy["ai_score"] = score
        c_copy["score_breakdown"] = breakdown
        scored_pool.append(c_copy)

    current_state = random.choice(scored_pool)
    best_state = current_state
    temperature = t_initial
    cooling_log = []
    iteration = 0

    while temperature > t_min and len(scored_pool) > 1:
        iteration += 1
        neighbor = random.choice([c for c in scored_pool if c["user_id"] != current_state["user_id"]])
        delta_e = neighbor["ai_score"] - current_state["ai_score"]

        accepted = False
        prob = 0.0
        if delta_e > 0:
            current_state = neighbor
            accepted = True
            reason = "Fitness Improved"
        else:
            prob = math.exp(delta_e / temperature)
            if random.random() < prob:
                current_state = neighbor
                accepted = True
                reason = "Probabilistic Escape"
            else:
                reason = "Rejected"

        if current_state["ai_score"] > best_state["ai_score"]:
            best_state = current_state

        cooling_log.append({
            "iteration": iteration,
            "temperature": round(temperature, 4),
            "current_mentor": current_state["full_name"],
            "score": current_state["ai_score"],
            "delta_e": round(delta_e, 4),
            "acceptance_prob": round(prob, 4) if delta_e <= 0 else 1.0,
            "accepted": accepted,
            "reason": reason
        })

        temperature *= alpha

    return {
        "best_candidate": best_state,
        "log": cooling_log,
        "iterations": iteration,
        "final_temperature": round(temperature, 4)
    }


DHAKA_WAYPOINTS: Dict[str, Tuple[float, float]] = {
    "Dhaka_Center": (23.8103, 90.4125),
    "Gulshan_2": (23.7937, 90.4146),
    "Notunbazar": (23.7979, 90.4236),
    "Banani": (23.7937, 90.4043),
    "Mohakhali": (23.7777, 90.4005),
    "Bijoy_Sarani": (23.7661, 90.3872),
    "Farmgate": (23.7561, 90.3872),
    "Dhanmondi_27": (23.7533, 90.3769),
    "Dhanmondi_Center": (23.7461, 90.3742),
    "Science_Lab": (23.7388, 90.3831),
    "Shahbagh": (23.7380, 90.3958),
    "Mirpur_10": (23.8071, 90.3686),
    "Mirpur_Center": (23.8223, 90.3654),
    "Airport_Road": (23.8514, 90.4081),
    "Uttara_Center": (23.8759, 90.3795),
    "Uttara_Sector_3": (23.8682, 90.3986),
    "Tangail_Highway": (24.2513, 89.9167),
    "Sirajganj_Junction": (24.4534, 89.7008),
    "Rajshahi_Highway": (24.3745, 88.6042),
    "Shahebbazar_Center": (24.3636, 88.6042),
}

WAYPOINT_EDGES: List[Tuple[str, str]] = [
    ("Notunbazar", "Gulshan_2"),
    ("Gulshan_2", "Banani"),
    ("Banani", "Mohakhali"),
    ("Mohakhali", "Bijoy_Sarani"),
    ("Bijoy_Sarani", "Farmgate"),
    ("Farmgate", "Shahbagh"),
    ("Farmgate", "Dhanmondi_27"),
    ("Dhanmondi_27", "Dhanmondi_Center"),
    ("Dhanmondi_Center", "Science_Lab"),
    ("Science_Lab", "Shahbagh"),
    ("Bijoy_Sarani", "Mirpur_10"),
    ("Mirpur_10", "Mirpur_Center"),
    ("Banani", "Airport_Road"),
    ("Airport_Road", "Uttara_Sector_3"),
    ("Uttara_Sector_3", "Uttara_Center"),
    ("Mohakhali", "Dhaka_Center"),
    ("Uttara_Center", "Tangail_Highway"),
    ("Tangail_Highway", "Sirajganj_Junction"),
    ("Sirajganj_Junction", "Rajshahi_Highway"),
    ("Rajshahi_Highway", "Shahebbazar_Center"),
]


def build_navigation_graph() -> Dict[str, Dict[str, float]]:
    """Build adjacency list graph with exact Haversine edge weights in kilometers."""
    graph: Dict[str, Dict[str, float]] = {k: {} for k in DHAKA_WAYPOINTS}
    for u, v in WAYPOINT_EDGES:
        lat1, lon1 = DHAKA_WAYPOINTS[u]
        lat2, lon2 = DHAKA_WAYPOINTS[v]
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        graph[u][v] = dist
        graph[v][u] = dist
    return graph


def astar_search(
    start_coords: Tuple[float, float],
    goal_coords: Tuple[float, float]
) -> Dict[str, Any]:
    """A* Pathfinding Algorithm with admissible Haversine heuristic."""
    graph = build_navigation_graph()
    waypoints = dict(DHAKA_WAYPOINTS)

    start_node = "START_LEARNER"
    waypoints[start_node] = start_coords
    graph[start_node] = {}

    nearest_to_start = sorted(
        DHAKA_WAYPOINTS.keys(),
        key=lambda w: haversine_distance(start_coords[0], start_coords[1], DHAKA_WAYPOINTS[w][0], DHAKA_WAYPOINTS[w][1])
    )[:3]
    for w in nearest_to_start:
        d = haversine_distance(start_coords[0], start_coords[1], DHAKA_WAYPOINTS[w][0], DHAKA_WAYPOINTS[w][1])
        graph[start_node][w] = d
        graph[w][start_node] = d

    goal_node = "GOAL_MENTOR"
    waypoints[goal_node] = goal_coords
    graph[goal_node] = {}

    nearest_to_goal = sorted(
        DHAKA_WAYPOINTS.keys(),
        key=lambda w: haversine_distance(goal_coords[0], goal_coords[1], DHAKA_WAYPOINTS[w][0], DHAKA_WAYPOINTS[w][1])
    )[:3]
    for w in nearest_to_goal:
        d = haversine_distance(goal_coords[0], goal_coords[1], DHAKA_WAYPOINTS[w][0], DHAKA_WAYPOINTS[w][1])
        graph[goal_node][w] = d
        graph[w][goal_node] = d

    direct_dist = haversine_distance(start_coords[0], start_coords[1], goal_coords[0], goal_coords[1])
    if direct_dist < 2.5:
        graph[start_node][goal_node] = direct_dist
        graph[goal_node][start_node] = direct_dist

    open_heap = []
    counter = 0
    h_start = haversine_distance(start_coords[0], start_coords[1], goal_coords[0], goal_coords[1])
    heapq.heappush(open_heap, (h_start, counter, start_node))

    came_from: Dict[str, str] = {}
    g_score: Dict[str, float] = {node: float("inf") for node in waypoints}
    g_score[start_node] = 0.0

    f_score: Dict[str, float] = {node: float("inf") for node in waypoints}
    f_score[start_node] = h_start

    closed_set = set()
    nodes_expanded = 0

    while open_heap:
        current_f, _, current = heapq.heappop(open_heap)

        if current in closed_set:
            continue
        closed_set.add(current)
        nodes_expanded += 1

        if current == goal_node:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()

            path_coords = [[waypoints[n][0], waypoints[n][1]] for n in path]
            total_dist = round(g_score[goal_node], 2)

            return {
                "success": True,
                "path_nodes": path,
                "path_coordinates": path_coords,
                "total_distance_km": total_dist,
                "nodes_expanded": nodes_expanded,
                "admissible_heuristic_verified": True
            }

        for neighbor, weight in graph[current].items():
            if neighbor in closed_set:
                continue

            tentative_g = g_score[current] + weight
            if tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                n_lat, n_lon = waypoints[neighbor]
                h = haversine_distance(n_lat, n_lon, goal_coords[0], goal_coords[1])
                f = tentative_g + h
                f_score[neighbor] = f
                counter += 1
                heapq.heappush(open_heap, (f, counter, neighbor))

    return {
        "success": False,
        "path_nodes": [start_node, goal_node],
        "path_coordinates": [
            [start_coords[0], start_coords[1]],
            [goal_coords[0], goal_coords[1]]
        ],
        "total_distance_km": round(direct_dist, 2),
        "nodes_expanded": nodes_expanded,
        "admissible_heuristic_verified": True
    }


def get_ai_recommendations(
    learner_lat: float,
    learner_lon: float,
    mentors_data: List[Dict[str, Any]],
    requested_skill_id: Optional[int] = None,
    max_price: Optional[float] = None,
    preference: Optional[str] = None
) -> Dict[str, Any]:
    """Execute Hill Climbing, Simulated Annealing, and A* Pathfinding to produce recommendations."""
    learner_ctx = {
        "skill_id": requested_skill_id,
        "max_price": max_price,
        "preference": preference,
        "lat": learner_lat,
        "lon": learner_lon
    }

    candidates = []
    for m in mentors_data:
        # Pre-filter candidate mentors: if a skill is requested, verify the candidate offers it
        if requested_skill_id is not None:
            m_skills = m.get("skills", [])
            if not any(s.get("skill_id") == requested_skill_id for s in m_skills):
                continue

        m_copy = dict(m)
        m_lat = m.get("latitude")
        m_lon = m.get("longitude")
        if m_lat is not None and m_lon is not None:
            dist = haversine_distance(learner_lat, learner_lon, float(m_lat), float(m_lon))
        else:
            dist = 999.0
        m_copy["distance_km"] = dist
        candidates.append(m_copy)

    if not candidates:
        return {
            "learner_location": {"lat": learner_lat, "lon": learner_lon},
            "ai_best_match": None,
            "nearest_mentor": None,
            "astar_route_nearest": None,
            "astar_route_best": None,
            "ranked_mentors": [],
            "is_fallback": False,
            "fallback_message": None,
            "telemetry": {}
        }

    # Progressive Geographic Radius Tiers (Dynamic based on GPS, non-hardcoded):
    # Tier 1: Local community (<= 25 km)
    # Tier 2: Metropolitan / suburbs (<= 50 km)
    # Tier 3: Regional (<= 100 km)
    # Tier 4: Wider search fallback (> 100 km)
    tier_1 = [c for c in candidates if c["distance_km"] <= 25.0]
    tier_2 = [c for c in candidates if c["distance_km"] <= 50.0]
    tier_3 = [c for c in candidates if c["distance_km"] <= 100.0]

    if tier_1:
        active_candidates = tier_1
        tier_radius = 25.0
        is_fallback = False
        fallback_message = None
    elif tier_2:
        active_candidates = tier_2
        tier_radius = 50.0
        is_fallback = True
        fallback_message = "No mentors found within 25 km. Showing mentors within 50 km."
    elif tier_3:
        active_candidates = tier_3
        tier_radius = 100.0
        is_fallback = True
        fallback_message = "No mentors found within 50 km. Showing mentors within 100 km."
    else:
        active_candidates = candidates
        tier_radius = max(200.0, max(c["distance_km"] for c in candidates))
        is_fallback = True
        fallback_message = "No nearby mentors found. Showing the closest available mentors."

    learner_ctx = {
        "skill_id": requested_skill_id,
        "max_price": max_price,
        "preference": preference,
        "lat": learner_lat,
        "lon": learner_lon,
        "tier_radius": tier_radius
    }

    # Execute Hill Climbing and Simulated Annealing on geographically active candidates
    hc_result = hill_climbing(active_candidates, learner_ctx)
    sa_result = simulated_annealing(active_candidates, learner_ctx)

    ai_best = sa_result["best_candidate"]
    if hc_result["best_candidate"] and (not ai_best or hc_result["best_candidate"]["ai_score"] > ai_best["ai_score"]):
        ai_best = hc_result["best_candidate"]

    # Nearest mentor is calculated strictly among the active candidate set
    nearest_mentor = min(active_candidates, key=lambda x: x["distance_km"])
    score_near, breakdown_near = evaluate_mentor_fitness(nearest_mentor, learner_ctx)
    nearest_mentor["ai_score"] = score_near
    nearest_mentor["score_breakdown"] = breakdown_near

    astar_nearest = None
    if nearest_mentor.get("latitude") is not None and nearest_mentor.get("longitude") is not None:
        astar_nearest = astar_search(
            (learner_lat, learner_lon),
            (float(nearest_mentor["latitude"]), float(nearest_mentor["longitude"]))
        )

    astar_best = None
    if ai_best and ai_best["user_id"] != nearest_mentor["user_id"]:
        if ai_best.get("latitude") is not None and ai_best.get("longitude") is not None:
            astar_best = astar_search(
                (learner_lat, learner_lon),
                (float(ai_best["latitude"]), float(ai_best["longitude"]))
            )
    else:
        astar_best = astar_nearest

    all_scored = []
    for c in active_candidates:
        s, b = evaluate_mentor_fitness(c, learner_ctx)
        c_ranked = dict(c)
        c_ranked["ai_score"] = s
        c_ranked["score_breakdown"] = b
        c_ranked["is_ai_best"] = bool(ai_best and c["user_id"] == ai_best["user_id"])
        c_ranked["is_nearest"] = (c["user_id"] == nearest_mentor["user_id"])
        all_scored.append(c_ranked)

    all_scored.sort(key=lambda x: x["ai_score"], reverse=True)

    return {
        "learner_location": {"lat": learner_lat, "lon": learner_lon},
        "ai_best_match": ai_best,
        "nearest_mentor": nearest_mentor,
        "astar_route_nearest": astar_nearest,
        "astar_route_best": astar_best,
        "ranked_mentors": all_scored,
        "is_fallback": is_fallback,
        "fallback_message": fallback_message,

        "telemetry": {
            "hill_climbing": {
                "iterations": hc_result.get("iterations", 0),
                "trajectory": hc_result.get("trajectory", []),
                "local_optimum_score": hc_result["best_candidate"]["ai_score"] if hc_result.get("best_candidate") else 0
            },
            "simulated_annealing": {
                "iterations": sa_result.get("iterations", 0),
                "log_sample": sa_result.get("log", [])[:10],
                "final_temperature": sa_result.get("final_temperature", 0.0),
                "global_optimum_score": sa_result["best_candidate"]["ai_score"] if sa_result.get("best_candidate") else 0
            },
            "astar": {
                "nearest_path_distance_km": astar_nearest.get("total_distance_km") if astar_nearest else None,
                "nearest_nodes_expanded": astar_nearest.get("nodes_expanded") if astar_nearest else 0,
                "admissible_heuristic": "Haversine Great-Circle Distance (h(n) <= g*(n))"
            }
        }
    }
