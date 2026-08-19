import { HubPage } from '../../components/ui/hub-page'

const communicationLinks = [
  { label: 'Compose Message', description: 'Create and send a new message', route: '/communications/compose', icon: 'M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z' },
  { label: 'Templates', description: 'Manage message templates', route: '/communications/templates', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
  { label: 'Sent Messages', description: 'View previously sent messages', route: '/communications/sent', icon: 'M12 19l9 2-9-18-9 18 9-2zm0 0v-8' },
]

export function CommunicationsHubPage() {
  return (
    <HubPage
      eyebrow="Communications"
      title="Communications"
      subtitle="Send messages, manage templates, and view communication history"
      stats={[]}
      links={communicationLinks}
    />
  )
}

export default CommunicationsHubPage
