import { Card, Typography } from '@douyinfe/semi-ui'

const { Title, Text } = Typography

function ResultPage() {
  return (
    <Card style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center', padding: 60 }}>
      <Title heading={3}>계산 완료</Title>
      <Text type="tertiary" style={{ marginTop: 8, display: 'block' }}>
        계산이 완료되었습니다. 상세 결과는 곧 표시됩니다.
      </Text>
    </Card>
  )
}

export default ResultPage
