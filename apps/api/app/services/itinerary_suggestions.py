from itertools import combinations

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError, StructuredOutputProvider
from app.core.config import settings
from app.models.entities import Experience, POI
from app.schemas.planner import ItineraryRankingResponse, PlanRequest
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from app.services.planner_engine import HeuristicPlanner, SuggestionPlanner
from app.services.planner_service import NoFeasiblePlan, PlannerService
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner


STYLES = ('balanced', 'budget', 'nearby', 'relaxed', 'interests')


def suggest_itineraries(db, request: PlanRequest):
    """Find distinct feasible previews, keeping as many explicit experience picks as possible."""
    original_experience_locks = request.locked_experience_ids
    original_poi_locks = request.locked_poi_ids
    all_locks = [('experience', item) for item in original_experience_locks]
    all_locks.extend(('poi', item) for item in original_poi_locks)
    lock_scenarios = [(original_experience_locks, original_poi_locks)]
    for remove_count in range(1, len(all_locks) + 1):
        for removed in combinations(all_locks, remove_count):
            removed_set = set(removed)
            experiences = [item for item in original_experience_locks if ('experience', item) not in removed_set]
            pois = [item for item in original_poi_locks if ('poi', item) not in removed_set]
            lock_scenarios.append((experiences, pois))
            if len(lock_scenarios) >= 32:
                break
        if len(lock_scenarios) >= 32:
            break
    # Always try the fully flexible fallback even when the user's pins exceed
    # the bounded subset search above.
    if not lock_scenarios or lock_scenarios[-1] != ([], []):
        lock_scenarios.append(([], []))
    lock_scenarios = list(dict.fromkeys(
        (tuple(experiences), tuple(pois)) for experiences, pois in lock_scenarios
    ))

    # Test the most-preserving set first. Only branch into style and activity
    # diversity after finding a feasible selection, so retries are not wasted
    # on five equivalent failures when a previous pick blocks the schedule.
    queue = [request.model_copy(update={
        'planning_style': 'balanced',
        'routing_mode': 'configured',
        'locked_experience_ids': list(locked),
        'locked_poi_ids': list(locked_pois),
        'excluded_experience_ids': [],
    }) for locked, locked_pois in lock_scenarios]
    planner = PlannerService(db)
    seen_requests, seen_routes, expanded_styles, options = set(), set(), set(), []
    last_error = None
    attempts = 0
    while queue and len(options) < 5 and attempts < 40:
        candidate = queue.pop(0)
        key = (candidate.planning_style, tuple(sorted(candidate.locked_experience_ids)),
               tuple(sorted(candidate.locked_poi_ids)), tuple(sorted(candidate.excluded_experience_ids)))
        if key in seen_requests:
            continue
        seen_requests.add(key)
        attempts += 1
        try:
            planner.engine = SuggestionPlanner(candidate.planning_style) if candidate.planning_style != 'balanced' else HeuristicPlanner()
            preview = planner.plan(candidate, persist=False)
            # Unsaved previews have no stored itinerary; the request id identifies the option until one is confirmed.
            preview['itinerary_id'] = preview['request_id']
        except NoFeasiblePlan as error:
            # Report diagnostics from the most relaxed attempt. Returning the
            # first error can falsely blame a pin even after it was released.
            last_error = error
            continue

        signature = tuple(stop['experience_id'] for stop in preview['stops'])
        if signature not in seen_routes:
            seen_routes.add(signature)
            included_experience_ids = {stop['experience_id'] for stop in preview['stops']}
            included_poi_ids = {stop['poi']['id'] for stop in preview['stops']}
            relaxed_ids = set(original_experience_locks) - included_experience_ids
            relaxed_names = [experience.name for experience in db.query(Experience).filter(Experience.id.in_(relaxed_ids)).all()] if relaxed_ids else []
            relaxed_poi_ids = set(original_poi_locks) - included_poi_ids
            relaxed_poi_names = [poi.name for poi in db.query(POI).filter(POI.id.in_(relaxed_poi_ids)).all()] if relaxed_poi_ids else []
            options.append({'style': candidate.planning_style, 'relaxed_experience_names': relaxed_names,
                            'relaxed_poi_names': relaxed_poi_names, 'request': candidate, 'preview': preview})

        lock_key = (tuple(sorted(candidate.locked_experience_ids)), tuple(sorted(candidate.locked_poi_ids)))
        if lock_key not in expanded_styles:
            expanded_styles.add(lock_key)
            styles = [candidate.model_copy(update={'planning_style': style}) for style in STYLES if style != candidate.planning_style]
            # First evaluate every way of keeping or relaxing the user's pins.
            # Style variants are secondary: they often produce the same route
            # and otherwise consume the bounded search budget before distinct
            # feasible pin combinations are considered.
            queue.extend(styles)

        # Explore alternatives by excluding one optional stop from the last
        # feasible preview. User-selected pins and POI pins remain protected.
        for stop in preview['stops']:
            if stop['experience_id'] in candidate.locked_experience_ids or stop['poi']['id'] in request.locked_poi_ids:
                continue
            excluded = sorted(set(candidate.excluded_experience_ids) | {stop['experience_id']})
            if len(excluded) <= 100 and len(queue) < 40:
                queue.append(candidate.model_copy(update={'excluded_experience_ids': excluded}))

    if not options and last_error:
        raise last_error
    return {'options': options, 'requested_count': 5, 'returned_count': len(options), 'ranking_source': 'heuristic'}


def rank_suggestions_with_gemini(db, request: PlanRequest, result: dict, provider: StructuredOutputProvider):
    """Let Gemini rank and explain only backend-validated itineraries."""
    if not result['options'] or provider.model_name == 'not-configured':
        return result
    try:
        selected_provider = (resolve_integration_value(db, 'ai', 'provider') or settings.llm_provider).strip().lower()
    except IntegrationSecretConfigurationError:
        return result
    if selected_provider != 'gemini':
        return result

    options = result['options']
    option_ids = [option['preview']['itinerary_id'] for option in options]
    by_id = {option_id: option for option_id, option in zip(option_ids, options)}
    context = {
        'user_criteria': {
            'start_at': request.start_at.isoformat(),
            'end_at': request.end_at.isoformat(),
            'group_size': request.group_size,
            'budget_vnd': request.budget_vnd,
            'transport_mode': request.transport_mode,
            'intent_weights': request.intent_weights,
        },
        'feasible_options': [
            {
                'option_id': option_id,
                'stops': [
                    {
                        'experience_id': stop['experience_id'],
                        'name': stop['name'],
                        'category': stop['category'],
                        'start_at': stop['start_at'].isoformat(),
                        'end_at': stop['end_at'].isoformat(),
                        'cost_vnd': stop['cost_vnd'],
                    }
                    for stop in option['preview']['stops']
                ],
                'estimated_cost_vnd': option['preview']['estimated_cost_vnd'],
                'travel_minutes': option['preview']['total_travel_min'],
                'estimated_return_at': option['preview']['estimated_return_at'].isoformat() if option['preview']['estimated_return_at'] else None,
                'relaxed_experience_names': option['relaxed_experience_names'],
                'relaxed_poi_names': option['relaxed_poi_names'],
            }
            for option_id, option in zip(option_ids, options)
        ],
    }
    try:
        ranked = PromptRunner(provider).run('ITINERARY_RANKER', context, ItineraryRankingResponse)
    except (LLMNotConfigured, LLMProviderError, InvalidStructuredOutput, KeyError, ValueError):
        return result

    ranked_ids = [item.option_id for item in ranked.ranked_options]
    if len(ranked_ids) != len(option_ids) or set(ranked_ids) != set(option_ids):
        return result
    result['options'] = [
        {**by_id[item.option_id], 'recommendation_reason': item.reason_vi}
        for item in ranked.ranked_options
    ]
    result['ranking_source'] = 'gemini'
    return result
