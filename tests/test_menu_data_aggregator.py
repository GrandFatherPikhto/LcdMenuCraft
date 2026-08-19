"""Unit tests for ``MenuDataAggregator`` (plan item P2/A1).

The aggregator derives all aggregated menu structures from the flattened
node list and memoizes them with ``functools.cached_property``. These tests
lock in that behaviour and verify that ``MenuCraft`` delegates to the
very same aggregator object while keeping its public API intact.
"""


def test_aggregator_builds_from_flat_nodes(menu_flattener):
    """The aggregator can be constructed directly from the flat nodes."""
    from generate_menu.menu_data_aggregator import MenuDataAggregator

    flat = menu_flattener.flatten()
    aggregator = MenuDataAggregator(flat)

    # 18 flat nodes total, minus the virtual root node.
    assert len(aggregator.menu) == 17
    # Every non-root node is either a leaf or a branch.
    assert len(aggregator.leafs) + len(aggregator.branches) == 17
    assert aggregator.first is not None
    assert aggregator.first.id == "start"


def test_aggregator_caches_results(menu_flattener):
    """cached_property returns the same object on repeated access."""
    from generate_menu.menu_data_aggregator import MenuDataAggregator

    flat = menu_flattener.flatten()
    aggregator = MenuDataAggregator(flat)

    assert aggregator.menu is aggregator.menu
    assert aggregator.functions is aggregator.functions
    assert aggregator.categories is aggregator.categories
    assert aggregator.required_functions is aggregator.required_functions
    assert aggregator.functions_by_event_type is aggregator.functions_by_event_type
    assert aggregator.functions_by_type_role is aggregator.functions_by_type_role


def test_processor_delegates_to_single_aggregator(monkeypatch, project_root, config_path):
    """MenuCraft exposes the aggregator and forwards every aggregation."""
    monkeypatch.chdir(project_root)

    from generate_menu.menucraft import MenuCraft

    processor = MenuCraft(str(config_path))

    # One aggregator instance for the whole processor lifetime.
    assert processor.data is processor._aggregator

    # Delegation returns the very same cached objects, not fresh copies.
    assert processor.menu is processor.data.menu
    assert processor.functions is processor.data.functions
    assert processor.categories is processor.data.categories
    assert processor.first is processor.data.first
    assert processor.required_functions is processor.data.required_functions
    assert processor.functions_by_event_type is processor.data.functions_by_event_type


def test_aggregator_matches_processor_results(monkeypatch, project_root, config_path):
    """The aggregator over the same nodes yields identical structures."""
    monkeypatch.chdir(project_root)

    from generate_menu.menucraft import MenuCraft
    from generate_menu.menu_data_aggregator import MenuDataAggregator

    processor = MenuCraft(str(config_path))
    # Use the processor's own nodes so embedded FlatNode objects match by
    # identity and full-dict comparison is valid.
    aggregator = MenuDataAggregator(processor._flat_nodes)

    assert aggregator.functions == processor.functions
    assert aggregator.categories == processor.categories
    assert aggregator.required_functions == processor.required_functions
    assert aggregator.custom_callbacks == processor.custom_callbacks
    assert aggregator.auto_generated_functions == processor.auto_generated_functions
    assert aggregator.detailed_callback_infos == processor.detailed_callback_infos
    assert aggregator.callback_summary_by_category == processor.callback_summary_by_category
    assert aggregator.functions_by_type == processor.functions_by_type
    assert aggregator.functions_by_role == processor.functions_by_role
    assert aggregator.functions_by_navigation == processor.functions_by_navigation
