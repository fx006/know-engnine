from sqlalchemy import JSON,Text

from know_engine_py.app.models.config import(
    DomainConfigModel,
    IntentConfigModel,
    PromptTemplateModel,
)

def test_domain_config_model_metadata():
    table = DomainConfigModel.__table__

    assert table.name == "domain_config"
    assert "domain_id" in table.columns
    assert "name" in table.columns
    assert "description" in table.columns
    assert "entity_schema" in table.columns
    assert "fallback_intent" in table.columns
    assert "is_active" in table.columns

def test_intent_config_model_has_unique_domain_intent_constraint():
    table = IntentConfigModel.__table__

    assert table.name == "intent_config"
    assert "domain_id" in table.columns
    assert "intent_name" in table.columns
    assert "retrieval_strategy" in table.columns
    assert "data_sources" in table.columns
    assert "sort_order" in table.columns
    assert "is_active" in table.columns

    constraints = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("domain_id", "intent_name") in constraints

def test_prompt_template_model_has_unique_versioned_prompt_constraint():
    table = PromptTemplateModel.__table__

    assert table.name == "prompt_template"
    assert "domain_id" in table.columns
    assert "intent_name" in table.columns
    assert "prompt_type" in table.columns
    assert "content" in table.columns
    assert "version" in table.columns
    assert "is_active" in table.columns
    assert isinstance(table.columns["content"].type, Text)

    constraints = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("domain_id", "intent_name", "prompt_type", "version") in constraints