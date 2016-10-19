package utilities


import epto.Application
import epto.Event
import java.net.InetAddress

/**
 * Implementation of an Application to test EpTO
 *
 * @property expectedEvents the number of events we expect to deliver
 * @see Application
 *
 * @author Jocelyn Thode
 */
class TesterApplication(ttl: Int, k: Int, trackerURL: String, var expectedEvents: Int = -1, val peerNumber: Int,
                        delta: Long, myIp: InetAddress, gossipPort: Int, pssPort: Int) :
        Application(ttl, k, trackerURL, delta, myIp, gossipPort, pssPort) {

    val totalEvents = expectedEvents

    /**
     * Delivers the event to STDOUT
     *
     * {@inheritDoc}
     */
    @Synchronized override fun deliver(event: Event) {
        expectedEvents--
        logger.info("Delivered: ${event.id}")
        logger.debug("Expected events: {}", expectedEvents)
        if (expectedEvents <= 0) {
            logger.info("All events delivered !")
        }
    }

    /**
     * {@inheritDoc}
     */
    override fun broadcast(event: Event) {
        logger.info("Sending: ${event.id}")
        peer.disseminationComponent.broadcast(event)
    }

    /**
     * {@inheritDoc}
     */
    override fun start() {
        Thread(peer).start()
        logger.info("Started: ${myIp.hostAddress}")
        logger.info("Peer ID: ${peer.uuid}")
        logger.info("Peer Number: $peerNumber")
        logger.info("TTL: ${peer.oracle.TTL}, K: ${peer.disseminationComponent.K}")
        logger.info("Delta: ${peer.disseminationComponent.delta}")
    }

    /**
     * {@inheritDoc}
     */
    override fun stop() {
        peer.stop()
        logger.info("Quitting EpTO tester")
        logger.info("Messages sent: ${peer.core.gossipMessagesSent}")
        logger.info("Messages received: ${peer.core.gossipMessagesReceived}")
        logger.info("Ratio of events delivered: ${(totalEvents - expectedEvents) / totalEvents.toDouble()}")
        logger.info("PSS messages sent: ${peer.core.pssMessagesSent}")
        logger.info("PSS messages received: ${peer.core.pssMessagesReceived}")
    }
}
