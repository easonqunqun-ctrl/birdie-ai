import 'package:flutter/material.dart';

import '../../../core/storage.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

enum LegalKind { terms, privacy }

const _legalMetaDate = '2026-05-29';

/// 用户协议 / 隐私政策：对照 client/src/pages/legal/*。
class LegalPage extends StatelessWidget {
  const LegalPage({super.key, required this.kind});
  final LegalKind kind;

  String get _title =>
      kind == LegalKind.terms ? '用户服务协议' : '隐私政策';

  @override
  Widget build(BuildContext context) {
    final sections =
        kind == LegalKind.terms ? _termsSections : _privacySections;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: Text(_title)),
      body: ListView(
        padding: EdgeInsets.fromLTRB(rpx(32), rpx(24), rpx(32), rpx(64)),
        children: [
          Text(_title,
              style: TextStyle(
                  fontSize: rpx(40),
                  fontWeight: FontWeight.w800,
                  color: BrandColors.primary)),
          SizedBox(height: rpx(8)),
          Text(
              '版本 ${AppStorage.currentTermsVersion} · 更新日期 $_legalMetaDate',
              style: TextStyle(
                  fontSize: rpx(24), color: BrandColors.textTertiary)),
          SizedBox(height: rpx(24)),
          Text(
            kind == LegalKind.terms
                ? '欢迎使用「领翼golf」相关产品与服务。「领翼golf」由北京思域界控股有限公司（下称「本公司」「我们」或「运营方」）运营。请您在注册登录或使用本产品前认真阅读本协议。本产品中的《隐私政策》构成本协议组成部分。'
                : '「领翼golf」App 及产品服务由北京思域界控股有限公司（下称「我们」或「本公司」）提供。请您在使用本产品前仔细阅读本政策，了解我们如何收集、使用、存储、共享和保护您的个人信息。',
            style: TextStyle(
                fontSize: rpx(28),
                height: 1.6,
                color: BrandColors.textSecondary),
          ),
          SizedBox(height: rpx(28)),
          for (final s in sections) ...[
            Text(s.title,
                style: TextStyle(
                    fontSize: rpx(32),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.primary)),
            SizedBox(height: rpx(12)),
            for (final p in s.paras)
              Padding(
                padding: EdgeInsets.only(bottom: rpx(12)),
                child: Text(p,
                    style: TextStyle(
                        fontSize: rpx(28),
                        height: 1.55,
                        color: BrandColors.textSecondary)),
              ),
            SizedBox(height: rpx(20)),
          ],
          Text(
            kind == LegalKind.terms
                ? '本协议解释权在法律允许范围内由北京思域界控股有限公司享有。如对条款有疑问，请以本页所载版本与日期的文本为准：$_legalMetaDate。'
                : '本政策适用于「领翼golf」相关产品与服务。生效日期以更新日期所载为准：$_legalMetaDate。\n特别提示：本产品含人工智能生成内容，请以科学、审慎态度参考，不可替代专业医疗处置或持证教练的现场指导。',
            style: TextStyle(
                fontSize: rpx(24),
                height: 1.5,
                color: BrandColors.textTertiary),
          ),
        ],
      ),
    );
  }
}

class _Section {
  const _Section(this.title, this.paras);
  final String title;
  final List<String> paras;
}

const _termsSections = <_Section>[
  _Section('一、服务内容', [
    '本产品为面向高尔夫爱好者的运动辅助工具，可能包括挥杆视频的计算机视觉辅助分析、AI 教练对话答疑、个性化训练内容与练习闭环、账户与配额管理、增值会员或服务包等，具体以您实际可用的功能为准。',
    '本产品所输出的分析评分、图示、文案与 AI 答复由算法与自动化处理生成，仅供您在一般运动场景中参考与学习，不构成医疗诊断、康复治疗建议或由专业高尔夫教练签署的个性化现场指导结论。您应结合自身健康状况与场地条件合理使用；如出现伤病不适应及时就医。',
  ]),
  _Section('二、账号与实名制', [
    '· 本产品当前依托微信开放平台提供的身份能力完成账号创建与校验，您同意遵守微信平台相关规则及服务条款。',
    '· 您对使用您微信身份在本产品内进行的一切操作行为负责；如因账号保管不善导致第三人使用而造成的损失，由您先行承担。',
    '· 您可在「我的」等入口按指引申请注销账号；注销将导致您无法再访问历史数据，具体数据处理规则以《隐私政策》为准。',
    '· 约球功能实名验证：使用约球相关功能前须完成实名验证。约球功能仅提供球友信息匹配与活动组织工具，不参与任何线下活动，不对线下见面过程中的人身安全、财产安全或纠纷承担责任。',
  ]),
  _Section('三、行为规范与内容合规', [
    '您在使用本产品时应遵守中华人民共和国相关法律法规，不得上传违法违规内容、破解爬虫、绕过配额或滥用 AI 资源等。我们有权依规则采取警告、封禁、中止服务等措施。',
  ]),
  _Section('四、AI 生成内容', [
    'AI 生成的文字与建议具有不确定性与瞬时性，不保证完全符合事实或无偏见，亦不代表本公司对任何具体问题作出承诺或背书。如因您轻信 AI 内容而采取的行为导致损失，在法律允许的最大范围内我们不承担明示或暗示的保证责任。',
  ]),
  _Section('五、知识产权', [
    '本产品内的软件、界面设计、训练素材等，除依法属于第三方或已由您享有的内容外，其知识产权归本公司或权利人所有。您对自行上传的原视频享有相应权利，并为使我们完成分析服务授予一项非独占、仅限实现本服务的许可。',
  ]),
  _Section('六、会员、付费与发票', [
    '资费标准、服务内容、计费周期以您下单时产品内展示及支付订单页面为准。微信支付及相关发票、争议处理遵照支付平台规则与国家监管要求。',
  ]),
  _Section('七、服务的变更、中止与免责', [
    '为维护安全、遵从监管或不可抗力原因，我们可能调整或中止部分功能。对于非因我方故意或重大过失导致的第三方链路故障，我们在法律允许范围内免责。',
  ]),
  _Section('八、协议的变更', [
    '我们可能更新本协议。若更新将影响您的实质性权利，我们将通过登录页、弹窗或公告等方式提示，必要时重新征求同意；您在更新生效后继续使用，视为接受修订后的协议。',
  ]),
  _Section('九、法律适用与争议解决', [
    '本协议适用中华人民共和国大陆地区法律。因本协议或使用本产品产生之争议，双方先友好协商；协商不成时，提交本公司住所地有管辖权的人民法院诉讼解决。',
  ]),
  _Section('十、联系我们', [
    '公司名称：北京思域界控股有限公司',
    '联系邮箱：easongolf@outlook.com',
    '您也可以通过产品内「意见反馈」与我们联系。',
  ]),
];

const _privacySections = <_Section>[
  _Section('一、我们收集的信息', [
    '· 账号信息：微信开放平台返回的标识信息（如 OpenID，及适用情形下的 UnionID）；您主动填写的昵称、头像、球龄与水平等。',
    '· 挥杆视频与分析数据：您主动上传的视频及为生成报告产生的中间数据（骨骼关键点、评分与报告文本等）。',
    '· 对话与服务交互：您与 AI 教练的聊天内容及摘要、练习建议等。',
    '· 使用与设备日志：错误码、耗时、设备型号、系统版本、网络类型等必要技术日志。',
    '· 位置信息（主动使用时）：添加附近球馆等功能并授权后获取大致地理位置。',
    '· 约球实名信息（使用约球时）：出生日期、微信授权手机号验证状态。',
    '· 付费与履约信息：订单编号、开通状态、履约时间等与交易直接相关的最少信息。',
  ]),
  _Section('二、我们如何使用这些信息', [
    '用于提供与维护产品、改进与安全、约球与附近球馆（在您同意后）、履行法定义务。在您未另行单独同意的前提下，我们不会将您的个人视频或可识别身份的内容用于与提供本产品服务无关的模型训练。',
  ]),
  _Section('三、对外提供与委托处理', [
    '我们可能与大模型服务、云与安全基础设施、微信生态与支付等合作方共享或委托处理必要信息，不会向第三方出售个人信息。',
  ]),
  _Section('四、存储地点、跨境与保存期限', [
    '默认在中国大陆境内存储。原始挥杆视频通常至多保留 30 天；分析报告在您持有账号期间一般予以保留；注销后依法删除或匿名化。',
  ]),
  _Section('五、您的权利', [
    '在满足法律法规的前提下，您可行使查阅、更正、删除、撤回授权等个人信息权利，我们将在合理期限内响应。',
  ]),
  _Section('六、未成年人保护', [
    '未满 14 周岁请在监护人同意后使用一般功能；约球相关功能仅向已满 14 周岁且完成手机号实名的用户开放。',
  ]),
  _Section('七、本政策的更新', [
    '若修订可能实质影响您的权利，我们将通过弹窗、公告等方式提示；在法律要求需重新取得同意的情形下，将重新征求明示同意。',
  ]),
  _Section('八、联系我们', [
    '公司名称：北京思域界控股有限公司',
    '联系邮箱：easongolf@outlook.com',
  ]),
];
