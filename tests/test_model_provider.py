from app.load_balancer import ModelLoadBalancer
from app.model_provider import LoadBalancedModelProvider
from app.models import Job

def test_default_targets_are_qwen_and_deepseek(monkeypatch):
    monkeypatch.delenv("MODEL_TARGETS", raising=False)
    lb = ModelLoadBalancer()
    assert [t.name for t in lb.targets] == ["qwen", "deepseek"]
    assert lb.targets[0].model.endswith("qwen3p7-plus")
    assert lb.targets[1].model.endswith("deepseek-v4-flash")
    assert [t.weight for t in lb.targets] == [3, 2]


def test_package_prompt_reviews_full_jd_without_inventing_facts():
    class FakeBalancer:
        def __init__(self): self.messages = None
        def chat(self, messages, **kwargs):
            self.messages = messages
            return '{"tailored_resume":"Hassan S resume","cover_letter":"Dear Example Corp","application_notes":"Verify requirements"}'

    balancer = FakeBalancer()
    job = Job(title='AI Engineer', company='Example Corp', url='https://example.com/jobs/1',
              description='Build RAG services and own production monitoring.',
              requirements=['Python', 'RAG', 'production monitoring'])
    package = LoadBalancedModelProvider(load_balancer=balancer).build_application_package(job)
    prompt = balancer.messages[1]['content']
    assert 'Review every part of the JD' in prompt
    assert 'Example Corp' in prompt
    assert all(requirement in prompt for requirement in job.requirements)
    assert package.company == 'Example Corp'
