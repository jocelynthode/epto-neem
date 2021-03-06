package epto.udp

import epto.Application
import epto.Event
import epto.libs.Utilities.logger
import epto.pss.PeerSamplingService.PeerInfo
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.*

/**
 * Class gossiping the EpTO messages
 *
 * @property core the Core
 *
 * @property K the gossip fanout
 *
 * @see Core
 */
class Gossip(val core: Core, val K: Int = 15) {

    private val logger by logger()


    //Ethernet MTU: 1500Bytes - 60Bytes for the max IP header - 8Bytes for the UDP header = 1432
    //An other acceptable size would be 508 (576Bytes - 68Bytes)
    // 576 comes from the minimum maximum reassembly buffer size
    internal val maxSize = 1432
    //an event is 40 Bytes max (id : 16Bytes, ts: 4Bytes, ttl: 4Bytes, srcId: 16Bytes)
    //We substract 4Bytes for the ball length
    private val maxEvents = (maxSize - 4) / 40
    internal var totalSplits = 0

    /**
     * Relay a ball of event to other EpTO peers
     *
     * @param nextBall the ball of events to send
     */
    fun relay(nextBall: List<Event>) {
        val kView = selectKFromView()
        val ballsToSend = Math.ceil(nextBall.size / maxEvents.toDouble()).toInt()

        logger.debug("Total Ball size in Events: {}", nextBall.size)
        logger.debug("Max Events: {}", maxEvents)
        logger.debug("KView size: {}, KView:  [{}]", kView.size, kView.joinToString())
        if (ballsToSend > 1) {
            relaySplitted(nextBall, ballsToSend, kView)
        } else {
            sendRelay(nextBall, kView)
        }
    }

    private fun sendRelay(nextBall: List<Event>, kView: ArrayList<PeerInfo>) {
        logger.debug("Relay Ball size in Events: {}", nextBall.size)
        val byteOut = ByteArrayOutputStream()
        val out = Application.conf.getObjectOutput(byteOut)
        try {
            out.writeInt(nextBall.size)
            nextBall.forEach { it.serialize(out) }
            out.flush()
        } catch (e: IOException) {
            logger.error("Exception while sending next ball", e)
        } finally {
            out.close()
        }

        logger.debug("Ball size in Bytes: {}", byteOut.size())
        if (byteOut.size() > maxSize) {
            logger.warn("Ball size is too big !")
        }
        kView.forEach {
            core.send(byteOut.toByteArray(), it.address)
        }
        logger.debug("Sent Ball")
    }

    private fun relaySplitted(values: List<Event>, ballsToSend: Int, kView: ArrayList<PeerInfo>) {
        var ballsNumber = ballsToSend
        totalSplits += ballsToSend
        var i = 0

        while (ballsNumber > 0) {
            logger.debug("ballsToSend: {}", ballsNumber)
            if (ballsNumber > 1) {
                sendRelay(values.subList(i, i + maxEvents), kView)
            } else {
                sendRelay(values.subList(i, values.size), kView)
            }
            ballsNumber--
            i += maxEvents
        }
    }

    private fun selectKFromView(): ArrayList<PeerInfo> {
        var kView = ArrayList<PeerInfo>()
        // We don't want the view to be modified during this time
        synchronized(core.pss.pssLock) {
            kView = ArrayList(core.pss.view)
        }
        if (kView.size < K) {
            logger.warn("View is smaller than size K ({})", core.pss.view.size)
            return kView
        }
        // As lists are small, this is no big deal
        Collections.shuffle(kView)
        return ArrayList(kView.subList(0,K))
    }
}


