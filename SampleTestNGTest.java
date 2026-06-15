import org.testng.Assert;
import org.testng.annotations.Test;

public class SampleTestNGTest {

    @Test
    public void shouldAddTwoNumbers() {
        int actual = add(2, 3);

        Assert.assertEquals(actual, 5, "2 + 3 should equal 5");
        System.out.println("Test 'shouldAddTwoNumbers' passed");
    }

    @Test(enabled = false)
    public void shouldDetectNonEmptyName() {
        String name = "Volodymyr";

        Assert.assertFalse(name.isBlank(), "Name should not be blank");
        System.out.println("Test 'shouldDetectNonEmptyName' passed");
    }

    private int add(int left, int right) {
        return left + right;
    }
}
