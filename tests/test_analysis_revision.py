import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bridge_service as service
from analysis_store import AnalysisConflict, analysis_version, atomic_json
from test_contracts import fixture


class DiscussionRevisionTests(unittest.TestCase):
    def setUp(self):
        workspace_runtime=Path(__file__).resolve().parents[1]/'runtime'
        self.temp=tempfile.TemporaryDirectory(prefix='revision-test-',dir=workspace_runtime)
        assert Path(self.temp.name).resolve().is_relative_to(workspace_runtime.resolve())
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=fixture()
        self.id=self.data['id']
        for name,value in [('RUNTIME',self.root),('SNAPSHOTS',{self.id:self.data})]:
            p=patch.object(service,name,value);p.start();self.addCleanup(p.stop)
        self.original=dict(title='原始判断',summary='原始讲解',schemaVersion=2,snapshotId=self.id,source='codex',generatedAt=1,
            identity=dict(label='待核实电路',reason='连接证据',status='hypothesis',confidence='medium',evidence=['真实端子连接'],limitations=['未仿真']),
            sections=[dict(id='input',title='输入级',devices=['M1','M2'],body='原来的输入级解释',effect='影响输入级')],caveats=['未实测'])
        atomic_json(self.root/('explanation-'+self.id+'.json'),self.original)
        self.proposal=copy.deepcopy(self.original)
        self.proposal.update(title='新理解',summary='根据讨论重新理解完整电路',contextNotes=['用户提供设计语境，尚未实测'])
        self.proposal['identity']['label']='修订后的功能'
        self.history=[dict(role='user',content='这是设计用途，请结合连接核实'),dict(role='assistant',content='连接支持此解释，但待仿真')]

    def reply(self,revision=True):
        return json.dumps(dict(answer='结合连接的回答',revision=dict(reason='用户设计语境与连接相符',analysis=self.proposal) if revision else None),ensure_ascii=False)

    def test_auto_sync_updates_identity_and_guide_and_survives_reload(self):
        pristine=copy.deepcopy(self.data)
        with patch.object(service,'codex_reply',return_value=self.reply()):
            result=service.chat(self.id,'请核实设计用途',[],{})
        self.assertEqual(result['revisionStatus'],'updated')
        self.assertEqual(service.cached_identity(self.id)['identity']['label'],'修订后的功能')
        self.assertEqual(service.cached_identity(self.id)['summary'],self.proposal['summary'])
        self.assertEqual(service.conversation(self.id)['messages'][-1]['content'],'结合连接的回答')
        self.assertEqual(self.data,pristine)
        rows=service.analysis_store().history(self.id)['revisions']
        self.assertEqual(len(rows),2)
        self.assertEqual(sum(r['active'] for r in rows),1)

    def test_ordinary_question_preserves_analysis_without_new_revision(self):
        with patch.object(service,'codex_reply',return_value=self.reply(False)):
            service.chat(self.id,'输入管增大如何影响噪声？',[],{})
        self.assertEqual(service.cached_identity(self.id),self.original)
        self.assertEqual(service.analysis_store().history(self.id)['revisions'],[])

    def test_auto_sync_off_preserves_chat_but_not_guide(self):
        with patch.object(service,'codex_reply',return_value=self.reply()):
            result=service.chat(self.id,'讨论设计用途',[],{},sync_explanation=False)
        self.assertEqual(result['revisionStatus'],'disabled')
        self.assertEqual(service.cached_identity(self.id),self.original)
        self.assertEqual(len(service.conversation(self.id)['messages']),2)

    def test_invalid_device_cannot_replace_guide_but_answer_is_saved(self):
        self.proposal['sections'][0]['devices']=['INVENTED_DEVICE']
        with patch.object(service,'codex_reply',return_value=self.reply()):
            result=service.chat(self.id,'讨论设计用途',[],{})
        self.assertEqual(result['revisionStatus'],'invalid')
        self.assertEqual(service.cached_identity(self.id),self.original)
        self.assertEqual(len(service.conversation(self.id)['messages']),2)

    def test_stale_analysis_cannot_overwrite_newer_conclusion(self):
        old_version=analysis_version(self.original)
        current=service.analysis_store().publish(self.id,self.proposal,expected=old_version,reason='新结论',source='codex-discussion')
        with self.assertRaises(AnalysisConflict):
            service.analysis_store().publish(self.id,self.original,expected=old_version,reason='迟到的旧分析',source='codex')
        self.assertEqual(service.cached_identity(self.id),current)

    def test_in_flight_reanalysis_returns_newer_discussion_result(self):
        def reply(prompt):
            service.analysis_store().publish(self.id,self.proposal,expected=analysis_version(self.original),reason='讨论先完成',source='codex-discussion')
            return json.dumps(self.original)
        with patch.object(service,'codex_reply',side_effect=reply):
            result=service.explain(self.id,force=True)
        self.assertEqual(result['identity']['label'],'修订后的功能')

    def test_restore_is_new_revision_and_can_be_undone(self):
        store=service.analysis_store()
        revised=store.publish(self.id,self.proposal,expected=analysis_version(self.original),reason='新结论',source='codex-discussion')
        restored=service.restore_analysis(self.id,analysis_version(self.original),revised['revisionId'])
        self.assertEqual(restored['analysis']['identity']['label'],'待核实电路')
        again=service.restore_analysis(self.id,revised['revisionId'],restored['analysis']['revisionId'])
        self.assertEqual(again['analysis']['identity']['label'],'修订后的功能')
        self.assertEqual(len(store.history(self.id)['revisions']),4)

    def test_old_restore_request_does_not_overwrite_new_version(self):
        store=service.analysis_store();old=analysis_version(self.original)
        revised=store.publish(self.id,self.proposal,expected=old,reason='新结论',source='codex-discussion')
        result=service.restore_analysis(self.id,old,old)
        self.assertEqual(result['revisionStatus'],'superseded')
        self.assertEqual(service.cached_identity(self.id),revised)

    def test_manual_sync_imports_old_discussion_and_persists_before_model_failure(self):
        with patch.object(service,'codex_reply',side_effect=RuntimeError('网络中断')):
            with self.assertRaises(RuntimeError): service.revise_from_discussion(self.id,self.history)
        self.assertEqual(service.conversation(self.id)['messages'],self.history)
        self.assertEqual(service.cached_identity(self.id),self.original)
        response=json.dumps(dict(apply=True,reason='连接支持新理解',analysis=self.proposal))
        with patch.object(service,'codex_reply',return_value=response):
            result=service.revise_from_discussion(self.id,[])
        self.assertEqual(result['revisionStatus'],'updated')

    def test_different_snapshots_keep_separate_discussions_and_analysis(self):
        other='f'*20
        service.save_conversation(other,[dict(role='user',content='另一个电路')])
        service.save_conversation(self.id,self.history)
        self.assertNotEqual(service.conversation(other),service.conversation(self.id))
        self.assertIsNone(service.cached_identity(other))
        for invalid in ['../outside','A'*20,'a'*19]:
            with self.assertRaises(ValueError): service.conversation(invalid)

    def test_persisted_history_is_authoritative_and_old_context_is_preserved(self):
        service.save_conversation(self.id,self.history)
        self.original['contextNotes']=['之前用户提供的设计语境']
        atomic_json(self.root/('explanation-'+self.id+'.json'),self.original)
        with patch.object(service,'codex_reply',return_value=self.reply()) as reply:
            service.chat(self.id,'继续核实',[],{})
        self.assertIn(self.history[0]['content'],reply.call_args[0][0])
        self.assertIn('之前用户提供的设计语境',service.cached_identity(self.id)['contextNotes'])

    def test_provider_failure_leaves_previous_guide_and_conversation_usable(self):
        service.save_conversation(self.id,self.history)
        with patch.object(service,'codex_reply',side_effect=RuntimeError('网络不可用')):
            with self.assertRaises(RuntimeError): service.chat(self.id,'继续',[],{})
        self.assertEqual(service.cached_identity(self.id),self.original)
        self.assertEqual(service.conversation(self.id)['messages'],self.history)


if __name__=='__main__': unittest.main()
