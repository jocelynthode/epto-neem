import epto.utilities.Event;
import mocks.MockApp;
import net.sf.neem.MulticastChannel;
import org.junit.After;
import org.junit.Assert;
import org.junit.Before;
import org.junit.Test;

import java.net.InetSocketAddress;
import java.util.UUID;

/**
 * Class testing the whole protocol
 */
public class ProtocolTest {

    private MockApp app;
    private MockApp app1;
    private MockApp app2;
    private MulticastChannel neem;
    private MulticastChannel neem1;
    private MulticastChannel neem2;

    private Event event;
    private Event event1;
    private Event event2;
    private Event event3;
    private Event event4;
    private Event event5;
    private Event event6;
    private Event event7;

    @Before
    public void setUp() throws Exception {

        final int ttl = 10;
        final int k = 2;

        event = new Event(new UUID(23333,233123),1,51,new UUID(1111,2222));
        event1 = new Event(new UUID(44444,324645),2,51,new UUID(4444,2222));
        event2 = new Event(new UUID(847392,848123),1,51,new UUID(4444,2222));
        event3 = new Event(new UUID(45775,233123),1,51,new UUID(2221,2222));
        event4 = new Event(new UUID(9823498,3409834),1,51,new UUID(11,32344));
        event5 = new Event(new UUID(439495775,34034),1,51,new UUID(22,34048488));
        event6 = new Event(new UUID(423441,340734),4,30,new UUID(2223345,34048488));
        event7 = new Event(new UUID(15546,98734732),2,30,new UUID(2223345,34048488));

        InetSocketAddress address10000 = new InetSocketAddress("localhost", 10000);
        InetSocketAddress address10001 = new InetSocketAddress("localhost", 10001);
        InetSocketAddress address10002 = new InetSocketAddress("localhost", 10002);

        neem = new MulticastChannel(address10000);
        neem1 = new MulticastChannel(address10001);
        neem2 = new MulticastChannel(address10002);

        neem.connect(address10001);
        neem.connect(address10002);
        neem1.connect(address10000);
        neem1.connect(address10002);
        neem2.connect(address10000);
        neem2.connect(address10001);

        app = new MockApp(neem, ttl, k);
        app1 = new MockApp(neem1, ttl, k);
        app2 = new MockApp(neem2, ttl, k);

        app.start();
        app1.start();
        app2.start();

    }

    @After
    public void tearDown() throws Exception {
        neem.close();
        neem1.close();
        neem2.close();
    }

    //TODO for now compare if order is the same everywhere maybe make it so we can compare order too
    @Test
    public void testProtocol() throws Exception {
        app.broadcast(new Event(new UUID(11911,22292),0,0,null));
        app1.broadcast(new Event(new UUID(112511,255222),0,0,null));
        app1.broadcast(new Event(new UUID(11151,225345222),0,0,null));
        app.broadcast(new Event(new UUID(1152311,22522),0,0,null));
        app2.broadcast(new Event(new UUID(19111,225422),0,0,null));
        app1.broadcast(new Event(new UUID(115511,22292),0,0,null));
        app.broadcast(new Event(new UUID(11234511,2222),0,0,null));
        app2.broadcast(new Event(new UUID(11,22252),0,0,null));

        int retry = 0;
        while(retry != 5 && app.events.size() != 8
                && app1.events.size() != 8
                && app2.events.size() != 8)
        {
            Thread.sleep(5000);
            retry++;
        }

        Assert.assertArrayEquals(app.events.toArray(), app1.events.toArray());
        Assert.assertArrayEquals(app1.events.toArray(), app2.events.toArray());

    }
}
