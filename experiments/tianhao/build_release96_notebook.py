"""Build the portable public review notebook; frozen real outputs, optional refit."""
from pathlib import Path
import nbformat as nb
ROOT=Path(__file__).resolve().parents[2];cells=[]
def add(title,source,details):
 cells.append(nb.v4.new_markdown_cell(title));c=nb.v4.new_code_cell(source.strip());cells.append(c)
 cells.append(nb.v4.new_markdown_cell('**本段代码说明**\n\n'+'\n\n'.join(f'- **{a}：** {b}' for a,b in zip(['目的与输入','处理方法与参数','如何阅读结果','检查与限制'],details)),metadata={'explains_code_cell':c.id}))
cells.append(nb.v4.new_markdown_cell('''# Tianhao Wu：96车道真实重跑与可复核交付 · 2026-11-04

本Notebook对应实际完成的**224候选、16监督臂+4基准、557160条预测**。默认离线复核本次真实产物，无需个人project.local.json、原始ZIP或模型二进制。设置RETRAIN=True并提供解压Release和认证来源缓存，可完整重新构建、调参和训练。

**96个冻结车道中94个产生拥堵事件；30452事件，27858已知30分钟标签。** 四组为本地→历史→日历→天气，Release缺逐日流量/占有率，不能混用旧24车道flow或跨队列分数。恢复目标为持续恢复确认，仍有Proposal定义和空间匹配待确认。测试此前已经接触，本次不宣称首次盲测。

保留原始训练manifest、历史源代码和配置；发布时的可移植修复另行记录，不篡改历史Git/运行身份。'''))
add('## 0. 从任意工作目录找到仓库', '''from pathlib import Path
import os,sys,json,inspect,hashlib
import numpy as np,pandas as pd
get_ipython().run_line_magic("matplotlib","inline")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from IPython.display import display,Code,Image
root_hint=Path(os.environ.get('TRAFFIC_REPOSITORY',Path.cwd())).resolve()
ROOT=next(p for p in [root_hint,*root_hint.parents] if (p/'pyproject.toml').exists() and (p/'src/traffic_recovery').is_dir())
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments/tianhao')]
from verify_release96 import verify_bundle
from run_extended_models import sha
A=ROOT/'experiments/tianhao/expanded96_20261104'
for font in ['PingFang SC','Arial Unicode MS','Noto Sans CJK SC']:
 if font in {f.name for f in fm.fontManager.ttflist}:plt.rcParams['font.family']=font;break
plt.rcParams['axes.unicode_minus']=False
print('仓库依赖已导入；公开结果可离线核验。')''',['固定当前仓库和产物目录。','依赖仓库标记，不使用作者机器路径；从外部目录运行可设置TRAFFIC_REPOSITORY。','代码与数据路径均相对仓库。','首次核验在读取任何指标之前执行。'])
add('## 1. SHA-256、历史代码和冻结配置', '''verification=verify_bundle()
print(verification)
publication=json.loads((A/'publication_manifest.json').read_text())
original=json.loads((A/'original_training_manifest.json').read_text())
print('历史训练身份：',original['run']['git'],'；历史运行秒数：',original['runtime_seconds'])
print('Release整包SHA256：',json.loads((A/'release_metadata.json').read_text())['assets'][0]['digest'])
display(pd.read_csv(A/'sources.csv')[['file','url','retrieved_at','sha256']])''',['先验证预测、指标、来源及所有配置与代码字节。','同时检查原始训练源码、锁文件和发布源码清单；历史dirty状态如实保留。','status通过指公开产物/指标/选择一致，来源共94份。','无模型二进制时不假称重新拟合或概率重放；原始本地重放记录单独保留。'])
add('## 2. 数据导入、标签与时间划分', '''pred=pd.read_parquet(A/'predictions.parquet')
base=pred.loc[pred.model.eq('majority_class')]
cohort=base.groupby('split').agg(known=('event_id','size'),positive=('y_true','sum'),unknown=('n_censored_in_split','first')).reindex(['train','validation','test'])
cohort['negative']=cohort.known-cohort.positive;cohort['events']=cohort.known+cohort.unknown
display(cohort)
assert cohort.events.sum()==30452 and cohort.known.sum()==27858 and cohort.unknown.sum()==2594
cohort[['negative','positive','unknown']].plot.bar(stacked=True,figsize=(10,4),rot=0);plt.ylabel('事件数');plt.show()
print('训练2023–2024；验证2025；测试2026年1–9月；2023年1月拟合参考速度。')''',['读取557160条真实预测，并从单一基准臂恢复评估分母。','未知标签数取已保存审计计数，不从仅含已知标签的预测表推断。','正/负/未知分开，事件数与观测行数不同。','有完整Release时CLI可额外逐事件核对真值和预测时间。'])
add('## 3. 特征构建：展示与历史运行对应的源码', '''for name in ['experiments/tianhao/prepare_local.py','experiments/tianhao/prepare_external.py','src/traffic_recovery/external/calendar.py']:
 print('历史运行源码：',name)
 display(Code((A/'training_code'/name).read_text(encoding='utf-8'),language='python'))
contract=json.loads((A/'configs/contract.json').read_text())
display(pd.DataFrame([{'特征组':g,'字段数':len(cols),'实际字段':', '.join(cols)} for g,cols in contract['feature_groups'].items()]))
print('发布CLI支持显式输入、两种Release目录布局和Windows普通账户；不依赖符号链接。')''',['说明历史速度、时钟、假期和天气的实际计算。','历史窗口四时点，年度事前发布版本，天气按捕获时间向后匹配并限龄60分钟。','冻结源码由原始运行SHA约束；不是不加区分地显示后来改过的函数。','可移植修复未修改特征公式。缺流量/占有率数值，flow_slots不是流量值。'])
add('### 3.1 新队列覆盖与真实事件示例', '''coverage=pd.read_csv(A/'coverage.csv')
display(coverage.loc[coverage.split.eq('all')&coverage.feature.isin(['calendar_all_fields','temperature_c','wind_speed_kmh','weather_both_values'])])
example=pd.read_csv(A/'feature_examples.csv')
display(example[['event_id','prediction_time','speed_ratio','speed_change_15m_ratio','speed_mean_15m_ratio','speed_slope_15m_ratio_per_min']])
display(Image(filename=str(A/'figures/03_real_event.png')))
print('示例曲线是本轮从Release重算并逐值校验后的冻结图；红线后只解释结果。')''',['展示插补前缺失、真实字段和本轮事件曲线。','覆盖分别采用全事件和已知标签分母；图与示例文件都有SHA。','预测前还须满足来源可用；图中未来部分不能入模。','King’s Park是区域代理，不能外推最近站或全港覆盖。'])
add('## 4. 模型配置与完整训练入口', '''for name in ['supervised_rules.json','extended_rules.json']:
 print('实际训练的冻结配置：',name);display(json.loads((A/'configs'/name).read_text()))
from traffic_recovery.models.extended_classifiers import make_extended_pipeline
display(Code(inspect.getsource(make_extended_pipeline),language='python'))
# 默认复核本轮已真实完成的训练结果。重训需显式提供以下本地路径。
RETRAIN=False
RELEASE_DIR=None
SOURCE_CACHE=None
M=A
if RETRAIN:
 if RELEASE_DIR is None or SOURCE_CACHE is None:raise ValueError('Set RELEASE_DIR and SOURCE_CACHE before retraining')
 from datetime import datetime,timezone
 from run_release96 import prepare,train
 from verify_workflow import verify_run
 output=ROOT/'data/local/tianhao96-reproduction'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 prepare(Path(RELEASE_DIR),Path(SOURCE_CACHE),output/'prepared')
 train(output/'prepared',Path(RELEASE_DIR),output/'models')
 M=output/'models'
 verify_run(M,output/'prepared/event_features.parquet',Path(RELEASE_DIR)/'processed/events.parquet')
 pred=pd.read_parquet(M/'predictions.parquet')
tuning=pd.read_csv(M/'tuning.csv');parameters=pd.read_csv(M/'selected_parameters.csv');selected=pd.read_csv(M/'validation_selected.csv')
assert len(tuning)==224 and len(parameters)==16
display(parameters[['model','feature_set','parameters','validation_log_loss']])
display(pd.DataFrame(json.loads((M/'model_summaries.json').read_text())))''',['展示实际网格与选中参数，并提供原始数据完整重训入口。','L2每组6、树24、L1为8、SVM18；验证log loss最小，阈值0.5，seed42。','SVM前段训练拟合、后段训练校准，样本数区别在summary明确列出。','默认没有重新训练；224候选确实在本轮历史运行中训练过。校准时完整基础Pipeline冻结，测试不选参。'])
add('## 5. 指标、ROC/PR与混淆矩阵', '''from sklearn.metrics import confusion_matrix,roc_curve,precision_recall_curve,roc_auc_score,average_precision_score
summary=pd.read_csv(M/'metrics_summary.csv');confusions=pd.read_csv(M/'confusion_matrices.csv')
chosen=summary.loc[summary.split.eq('test')].merge(selected[['model','feature_set']],on=['model','feature_set'],validate='one_to_one')
display(chosen[['model','feature_set','n','macro_f1','balanced_accuracy','roc_auc','pr_auc','log_loss']])
fig,axes=plt.subplots(1,2,figsize=(13,4))
for row in selected.itertuples():
 q=pred.loc[pred.model.eq(row.model)&pred.feature_set.eq(row.feature_set)&pred.split.eq('test')]
 fpr,tpr,_=roc_curve(q.y_true,q.y_score);precision,recall,_=precision_recall_curve(q.y_true,q.y_score)
 axes[0].plot(fpr,tpr,label=f'{row.model} AUC={roc_auc_score(q.y_true,q.y_score):.3f}')
 axes[1].plot(recall,precision,label=f'{row.model} AP={average_precision_score(q.y_true,q.y_score):.3f}')
axes[0].plot([0,1],[0,1],'--',color='gray');axes[0].set(xlabel='假阳性率',ylabel='真阳性率',title='测试ROC')
axes[1].axhline(q.y_true.mean(),ls='--',color='gray');axes[1].set(xlabel='召回率',ylabel='精确率',title='测试PR与正类比例')
for ax in axes:ax.legend(fontsize=8)
plt.tight_layout();plt.show()
fig,axes=plt.subplots(2,2,figsize=(10,8))
for ax,row in zip(axes.flat,selected.itertuples()):
 q=pred.loc[pred.model.eq(row.model)&pred.feature_set.eq(row.feature_set)&pred.split.eq('test')]
 cm=confusion_matrix(q.y_true,q.y_pred,labels=[0,1]);ax.imshow(cm,cmap='Blues')
 for (i,j),v in np.ndenumerate(cm):ax.text(j,i,str(v),ha='center',va='center',color='white' if v>cm.max()*.6 else 'black')
 ax.set(title=f'{row.model}; n={len(q)}',xlabel='预测',ylabel='真实',xticks=[0,1],yticks=[0,1])
plt.tight_layout();plt.show()''',['从公开真实预测重新计算图表。','每模型采用验证选中组，矩阵固定0未恢复、1恢复。','看Macro-F1、平均召回、AUC、AP和7008个测试事件的错误分布。','22.9%的正类比例与旧24车道不同，不能直接比较AP高低。'])
add('### 5.1 四组增益与过拟合', '''display(pd.read_csv(M/'feature_group_comparisons.csv'))
groups=['+'.join(list(contract['feature_groups'])[:i]) for i in range(1,5)]
fig,axes=plt.subplots(2,2,figsize=(13,8))
for ax,model in zip(axes.flat,selected.model):
 for split,style in [('train',':'),('validation','--'),('test','-')]:
  values=summary.loc[summary.model.eq(model)&summary.split.eq(split)].set_index('feature_set').reindex(groups)
  ax.plot(range(4),values.macro_f1,style,marker='o',label=split)
 ax.set(title=model,xticks=range(4),xticklabels=['本地','+历史','+日历','+天气'],ylabel='Macro-F1');ax.legend()
plt.tight_layout();plt.show()''',['比较相同事件上的递增特征。','同模型、同预测分母，五项增益全部保留。','训练/验证差距提示过拟合；新增信息不一定提升。','无置信区间和因果结论；calendar含时钟与星期，不只是假期。'])
add('## 6. 系数、稀疏性与错误分析', '''interpretation=pd.read_csv(M/'interpretation.csv')
for model in ['logistic_regression','logistic_l1','decision_tree']:
 fs=selected.loc[selected.model.eq(model),'feature_set'].iloc[0]
 values=interpretation.loc[interpretation.model.eq(model)&interpretation.feature_set.eq(fs)]
 display(values[['model','feature','value']])
display(pd.DataFrame(json.loads((M/'model_summaries.json').read_text())))
errors=pd.read_csv(M/'error_groups.csv').merge(selected[['model','feature_set']],on=['model','feature_set'],validate='many_to_one')
display(errors.loc[errors.dimension.eq('peak')]);display(errors.loc[errors.dimension.eq('detector_id')])
errors.loc[errors.dimension.eq('peak')].pivot(index='group',columns='model',values='error_rate').plot.bar(figsize=(10,4),rot=0);plt.ylabel('错误率');plt.show()
display(Image(filename=str(A/'figures/07_coefficients.png')))''',['解释模型和错误集中位置。','显示含零的L1系数、树重要性、校准角色摘要；高峰固定07–10、17–20。','分组同时查看n；非零系数不是独立因果贡献。','RBF SVM没有线性系数；检测器不等于道路，小样本组不能过度解释。'])
add('## 7. 最终核验和交接边界', '''final=verify_bundle();print(final)
print('实际历史本地概率重放：',json.loads((A/'original_local_verification.json').read_text())['max_pipeline_score_difference'])
print('公开审计默认不需要模型二进制；要重做概率重放，请完整重训并运行verify_workflow。')
print('组员旧24车道RF/HGB结果未混排；待96同队列预测交接。')''',['再次核验公开产物及来源/配置。','600指标、60个臂与split、224候选、557160预测及SHA对应。','status通过是已执行检查的范围，不替代全组科学定义批准。','原始数据ZIP、个人缓存和模型二进制未提交；恢复定义、邻居、雨量/事故/活动的限制继续保留。'])
n=nb.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
for c in cells:
 if c.cell_type=='code':compile(c.source,'cell','exec')
nb.write(n,ROOT/'notebooks/Tianhao_新版96车道_完整重跑_20261104.ipynb')
