/**
 * 《领翼golf 隐私政策》静态页
 *
 * 正式对外展示稿；重大事项（收集范围、共享方、留存规则等）如有调整须法务复核，
 * 并同步 bump `CURRENT_TERMS_VERSION`。
 * 须与微信公众平台《小程序用户隐私保护指引》等材料保持一致。
 *
 * 合规依据：
 *  - 《个人信息保护法》(PIPL)
 *  - 《微信小程序运营规范》
 *  - 《生成式人工智能服务管理暂行办法》
 */

import { FC } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import { CURRENT_TERMS_VERSION } from '@/utils/storage'
import './legal.scss'

const LEGAL_META_DATE = '2026-05-13'

const PrivacyPage: FC = () => {
  return (
    <ScrollView scrollY className='legal legal--privacy'>
      <View className='legal__inner'>
        <View className='legal__header'>
          <Text className='legal__title'>隐私政策</Text>
          <Text className='legal__meta'>
            版本 {CURRENT_TERMS_VERSION} · 更新日期 {LEGAL_META_DATE}
          </Text>
        </View>

        <View className='legal__intro'>
          「领翼golf」小程序及产品服务由北京思无界控股有限公司（下称「我们」或「本公司」）提供。
          我们依照法律法规要求保护您的个人信息。请您在使用本产品前仔细阅读本政策，了解我们如何收集、使用、
          存储、共享和保护您的个人信息，以及您享有的相关权利。
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>一、我们收集的信息</Text>
          <Text className='legal__paragraph'>
            在您使用本产品对应功能时，我们会依法收集为实现该功能所必要的信息：
          </Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              <Text className='legal__item-title'>账号信息：</Text>
              微信开放平台返回的标识信息（如 OpenID，及在适用情形下的 UnionID），用于账号注册、登录与安全校验；
              您在资料页主动填写的昵称、头像、高尔夫球龄与水平等非强制信息。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>挥杆视频与分析数据：</Text>
              您在挥杆分析功能中主动上传的视频；为生成报告而产生的中间数据（例如骨骼关键点、评分与结构化报告文本）。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>对话与服务交互：</Text>
              您与 AI 教练的聊天内容及由此产生的摘要、练习建议等；
              在您使用内容安全抽检等场景下，我们可能按监管要求对部分文本进行检测（仅用于风险控制与合规，不作营销用途）。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>使用与设备日志：</Text>
              为提高稳定性与兼容性，我们可能收集会话内必要的技术日志（如错误码、耗时、匿名化事件）、
              设备及环境信息（如设备型号、操作系统版本、微信小程序基础库版本、网络类型等）。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>付费与履约信息：</Text>
              若您购买会员或服务包，我们可能通过微信支付等平台获取订单编号、开通状态、履约时间等与交易直接相关的最少信息，
              具体以支付渠道提供的数据为准。
            </Text>
          </View>
          <Text className='legal__paragraph'>
            我们不会以「本产品核心功能之外的用途」为名，主动向您索要通讯录、精确位置信息、通讯录、相册全量读写、通话记录等与功能无关的系统权限，
            亦不会强求您填写与挥杆分析与训练无关的敏感个人信息。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>二、我们如何使用这些信息</Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              <Text className='legal__item-title'>提供与维护产品：</Text>
              完成登录校验、配额与风控；向您展示挥杆分析、训练内容与 AI 答疑；在您授权范围内完成会员开通与账务核对。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>改进与安全：</Text>
              在产品升级、性能优化与安全审计过程中，我们可能基于去标识或统计后的信息进行内部分析，
              并保留必要的技术与安全日志以满足合规与安全事件处置要求。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>履行法定义务：</Text>
              在法律法规要求或为配合有权机关合法调查的情形下进行处理与披露。
            </Text>
          </View>
          <Text className='legal__paragraph'>
            <Text className='legal__item-title'>关于模型训练的说明：</Text>
            在您未另行单独同意的前提下，我们不会将您的个人视频或可识别您身份的内容用于与「向您提供本产品服务」无关的人工智能模型训练或对外共享。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>三、对外提供与委托处理</Text>
          <Text className='legal__paragraph'>
            我们仅在为实现本政策所述目的、遵守法律法规且采取适当保护措施的前提下，
            与下列类型的合作方共享或委托处理信息（具体名录可能随技术服务调整而变更，我们会在能力范围内要求其履行保密与安全义务）：
          </Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              <Text className='legal__item-title'>大模型与语义服务：</Text>
              当您使用 AI 教练等文字类能力时，经加密传输向具备合法资质的第三方大模型服务提供者发送与您提问相关的最少文本上下文；
              挥杆视频的像素内容默认不会发往上述提供方用于「闲聊之外的无关用途」（除非未来单独功能向您说明并取得同意）。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>云与安全基础设施：</Text>
              包括但不限于对象存储、数据库、CDN、密钥与堡垒机、内容与风控检测等在中国大陆境内机房部署的服务，
              具体服务商以实现当前技术架构为准；我们要求其按合同与法律要求履行安全保护责任。
            </Text>
            <Text className='legal__item'>
              <Text className='legal__item-title'>微信生态与支付：</Text>
              您使用微信小程序登录与微信支付等服务时，信息处理同时受微信平台规则与用户授权范围约束，
              我们不控制微信客户端内的数据处理，仅以接口返回结果为履约依据。
            </Text>
          </View>
          <Text className='legal__paragraph'>
            我们不会向第三方出售或以营利为目的变相出售您的个人信息。除法律规定或取得您另行同意外，
            不会向与本产品无关的第三方共享可识别您身份的资料。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>四、存储地点、跨境与保存期限</Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              我们默认将在中国大陆境内采集与存储您的个人信息；
              如因业务必要确需进行跨境传输，我们将依法履行安全评估、标准合同或个人单独同意等程序，并在实施前以更显著方式向您说明。
            </Text>
            <Text className='legal__item'>
              {`原始挥杆视频在对象存储中通常保留至多 `}
              <Text className='legal__item-title'>30 天</Text>
              ，期满自动删除或匿名化；
              {`您也可在「我的 → 分析历史」中更早地删除对应记录（删除后我们通常无法在合理技术上恢复原件）。`}
            </Text>
            <Text className='legal__item'>
              {`分析报告、结构化训练数据等在您持有账号期间一般予以保留以便您回看；`}
              您注销账号后，我们会在法律要求的最短期限内删除或匿名化处理，依法需留存的账务、日志等按其法定保存年限处理。
            </Text>
          </View>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>五、您的权利</Text>
          <Text className='legal__paragraph'>
            在满足法律法规与微信平台规则的前提下，您可通过本产品内自助功能或与我们联系的方式，
            行使知情权、查阅复制权、更正权、删除权、撤回授权、索取解释说明等个人信息权利，
            我们将在合理期限内响应。若您对处理结果有异议，可依法向网信部门等有管辖权的机关申诉或投诉。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>六、未成年人保护</Text>
          <Text className='legal__paragraph'>
            若您未满 14 周岁，请在监护人同意后使用本产品；已满 14 周岁未满 18 周岁的，
            应在监护人陪同下阅读并理解本政策。若您作为监护人不同意被监护人向我们提供个人信息，请停止使用或联系我们删除。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>七、本政策的更新</Text>
          <Text className='legal__paragraph'>
            {`我们可能适时修订本政策。若修订可能实质影响您的权利（例如收集使用目的、共享方、保存期限发生重大变化），`}
            我们将通过本产品内弹窗、公告或其他合理方式进行提示；
            {`在法律要求需重新取得同意的情形下，我们将重新征求您的明示同意后再处理。`}
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>八、联系我们</Text>
          <Text className='legal__paragraph'>公司名称：北京思无界控股有限公司</Text>
          <Text className='legal__paragraph'>联系邮箱：easongolf@outlook.com</Text>
          <Text className='legal__paragraph'>
            您也可以通过小程序内「意见反馈」等入口与我们联系；我们将在核验身份后尽力在合理期限内答复。
          </Text>
        </View>

        <Text className='legal__footer'>
          {`本政策适用于「领翼golf」相关产品与服务。生效日期以更新日期所载为准：`}
          {LEGAL_META_DATE}。
          {
            `\n特别提示：本产品含人工智能生成内容，请以科学、审慎态度参考，不可替代专业医疗处置或持证教练的现场指导。`
          }
        </Text>
      </View>
    </ScrollView>
  )
}

export default PrivacyPage
